"""Service helpers for REST APIs, MQTT, and streaming responses."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict

from fastapi import HTTPException

from ihm.server import state
from ihm.server.config import USE_AI_ASSISTANT
from ihm.server.mqtt_manager import initialize_mqtt_client
from ihm.server.rest_api_client import kill_ai_assistant_agent, start_ai_assistant_agent


async def start_services_if_needed(active_count: int, user_id: str) -> None:
    """Start the AI Assistant via REST APIs when the first session connects."""
    if not USE_AI_ASSISTANT or active_count != 1 or state.docker_container_running:
        return

    await start_ai_assistant_agent(user_id=user_id)
    state.docker_container_running = True
    state.last_user_id = user_id
    await asyncio.sleep(2)
    if not initialize_mqtt_client():
        raise HTTPException(status_code=503, detail="MQTT client failed to initialize")


async def shutdown_services_if_idle(active_count: int, user_id: str) -> bool:
    """Stop the AI Assistant via REST APIs when there are no active sessions."""
    if active_count != 0:
        return False

    if state.mqtt_client_manager:
        state.mqtt_client_manager.disconnect()
        state.mqtt_client_manager = None
    if state.docker_container_running:
        await kill_ai_assistant_agent(user_id=user_id)
        state.docker_container_running = False
    return True


async def ensure_services_ready() -> None:
    """Ensure REST-backed services are running before handling a request."""
    if not USE_AI_ASSISTANT:
        return

    if not state.docker_container_running:
        user_id = next(iter(state.active_sessions.values()), {}).get("user_id", "1")
        await start_ai_assistant_agent(user_id=user_id)
        state.docker_container_running = True
        state.last_user_id = user_id

    if not initialize_mqtt_client():
        raise HTTPException(status_code=503, detail="MQTT client failed to initialize")


async def build_sse_stream(
    mqtt_task: asyncio.Task[Dict[str, Any]],
) -> AsyncGenerator[str, None]:
    """Yield SSE events while waiting for the MQTT response."""
    message_id = f"ai-{id(mqtt_task)}"
    yield format_sse_event({"type": "start-step"})
    yield format_sse_event({"type": "text-start", "id": message_id})

    while not mqtt_task.done():
        await asyncio.sleep(1)
        yield ": heartbeat\n\n"

    response = await mqtt_task
    answer_text = response.get("response", "") if isinstance(response, dict) else str(
        response
    )
    for word in answer_text.split():
        yield format_sse_event(
            {"type": "text-delta", "id": message_id, "delta": f"{word} "}
        )
        await asyncio.sleep(0.05)

    yield format_sse_event({"type": "text-end", "id": message_id})
    yield format_sse_event({"type": "finish-step"})
    yield format_sse_event({"type": "finish"})
    yield "data: [DONE]\n\n"


async def build_mock_stream(query: str) -> AsyncGenerator[str, None]:
    """Generate a short mock streaming response when the assistant is disabled."""
    message_id = f"mock-{hash(query)}"
    yield format_sse_event({"type": "start-step"})
    yield format_sse_event({"type": "text-start", "id": message_id})

    for word in "This is an example response from the mock server.".split():
        yield format_sse_event(
            {"type": "text-delta", "id": message_id, "delta": f"{word} "}
        )
        await asyncio.sleep(0.05)

    yield format_sse_event({"type": "text-end", "id": message_id})
    yield format_sse_event({"type": "finish-step"})
    yield format_sse_event({"type": "finish"})
    yield "data: [DONE]\n\n"


def format_sse_event(payload: Dict[str, Any]) -> str:
    """Serialize a JSON payload into a Server-Sent Event string."""
    return f"data: {json.dumps(payload)}\n\n"
