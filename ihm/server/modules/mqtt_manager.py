"""MQTT utilities for the FastAPI server."""

import asyncio
import json
import logging
import threading
import uuid
from typing import Any, Dict

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from fastapi import HTTPException

from ihm.server.config import MQTT_BROKER, MQTT_INPUT_TOPIC, MQTT_OUTPUT_TOPIC, MQTT_PORT
from ihm.server import state

logger = logging.getLogger(__name__)


class MQTTClientManager:
    """Manages MQTT connection and communication with the AI assistant agent."""

    def __init__(self, broker: str, port: int, input_topic: str, output_topic: str):
        self.broker = broker
        self.port = port
        self.input_topic = input_topic
        self.output_topic = output_topic

        self.client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self.pending_requests: Dict[str, threading.Event] = {}
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

        self.connected = False
        self.loop_started = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("MQTT client connected to %s:%s", self.broker, self.port)
            self.connected = True
            client.subscribe(self.output_topic, qos=2)
        else:
            logger.error("MQTT connection failed with code %s", rc)
            self.connected = False

    def _on_disconnect(self, client, userdata, rc, *args, **kwargs):
        logger.warning("MQTT client disconnected (rc=%s)", rc)
        self.connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            data = json.loads(payload)
            request_id = data.get("request_id")
            matched = False

            with self.lock:
                if request_id and request_id in self.pending_requests:
                    matched = True
                elif self.pending_requests:
                    request_id = list(self.pending_requests.keys())[0]
                    matched = True

                if matched:
                    self.responses[request_id] = data
                    self.pending_requests[request_id].set()
                else:
                    logger.warning("Received MQTT message without matching request_id: %s", data)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error processing MQTT message: %s", exc)

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            self.loop_started = True
        except Exception as exc:  # pragma: no cover - connection errors
            logger.exception("Error connecting to MQTT broker: %s", exc)
            raise

    def disconnect(self):
        if self.loop_started:
            self.client.loop_stop()
        if self.connected:
            self.client.disconnect()
        self.connected = False
        self.loop_started = False

    async def publish_and_wait(self, message: Dict[str, Any], timeout: int = 600) -> Dict[str, Any]:
        if not self.connected:
            raise HTTPException(status_code=503, detail="MQTT broker not connected")

        request_id = str(uuid.uuid4())
        message["request_id"] = request_id

        event = threading.Event()
        with self.lock:
            self.pending_requests[request_id] = event
            self.responses[request_id] = None

        try:
            message_json = json.dumps(message)
            result = self.client.publish(self.input_topic, message_json, qos=2)
            result.wait_for_publish(timeout=2)

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to publish MQTT message: return code {result.rc}",
                )

            loop = asyncio.get_event_loop()
            try:
                await asyncio.wait_for(loop.run_in_executor(None, event.wait), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise HTTPException(status_code=504, detail=f"MQTT response timeout after {timeout}s") from exc

            with self.lock:
                response = self.responses.get(request_id)
                if not response:
                    raise HTTPException(status_code=500, detail="No response received from MQTT")
                return response
        finally:
            with self.lock:
                self.pending_requests.pop(request_id, None)
                self.responses.pop(request_id, None)


def initialize_mqtt_client() -> bool:
    """Create and connect the MQTT client if it is not ready."""
    if state.mqtt_client_manager and state.mqtt_client_manager.connected:
        return True

    try:
        state.mqtt_client_manager = MQTTClientManager(
            broker=MQTT_BROKER,
            port=MQTT_PORT,
            input_topic=MQTT_INPUT_TOPIC,
            output_topic=MQTT_OUTPUT_TOPIC,
        )
        state.mqtt_client_manager.connect()
        return True
    except Exception as exc:  # pragma: no cover - connection errors
        logger.exception("Error initializing MQTT client: %s", exc)
        state.mqtt_client_manager = None
        return False
