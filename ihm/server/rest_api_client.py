"""HTTP client helpers for the AI Assistant REST APIs."""
from __future__ import annotations

import logging
from typing import Any, Dict

import httpx
from fastapi import HTTPException

from ihm.server.config import (
    AI_ASSISTANT_KILL_API_URL,
    AI_ASSISTANT_START_API_URL,
    INFERENCE_MODEL_NAME,
    MQTT_BROKER,
    MQTT_INPUT_TOPIC,
    MQTT_OUTPUT_TOPIC,
    MQTT_PORT,
)

logger = logging.getLogger(__name__)


def _coerce_user_id(user_id: str) -> int:
    """Convert a user id string into a stable integer for the REST APIs."""
    try:
        return int(user_id)
    except ValueError:
        return abs(hash(user_id)) % (10**8)


async def start_ai_assistant_agent(user_id: str) -> None:
    """Request the REST API to start the AI Assistant container."""
    payload: Dict[str, Any] = {
        "broker": MQTT_BROKER,
        "port": MQTT_PORT,
        "user_id": _coerce_user_id(user_id),
        "input_topic": MQTT_INPUT_TOPIC,
        "output_topic": MQTT_OUTPUT_TOPIC,
        "inference_model_name": INFERENCE_MODEL_NAME,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(AI_ASSISTANT_START_API_URL, json=payload)

    if response.status_code != 200:
        logger.error("Start REST API failed: %s", response.text)
        raise HTTPException(
            status_code=503,
            detail="AI Assistant REST API failed to start the container",
        )


async def kill_ai_assistant_agent(user_id: str) -> None:
    """Request the REST API to stop the AI Assistant container."""
    payload = {"user_id": _coerce_user_id(user_id)}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(AI_ASSISTANT_KILL_API_URL, json=payload)

    if response.status_code != 200:
        logger.error("Kill REST API failed: %s", response.text)
        raise HTTPException(
            status_code=503,
            detail="AI Assistant REST API failed to stop the container",
        )
