"""Service helpers for REST APIs, MQTT, and streaming responses."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict

from fastapi import HTTPException

from ihm.server import state
from ihm.server.config import USE_AI_ASSISTANT
from ihm.server.modules.mqtt_manager import initialize_mqtt_client
from ihm.server.modules.rest_api_client import kill_ai_assistant_agent, start_ai_assistant_agent


async def start_services_if_needed(user_id: str, session_id: str) -> None:
    """Start the AI Assistant via REST APIs for a specific session if not already running."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📦 START_SERVICES_IF_NEEDED - Session ID: {session_id}, User ID: {user_id}")
    print(f"📦 START_SERVICES_IF_NEEDED - Session ID: {session_id}, User ID: {user_id}")
    
    if not USE_AI_ASSISTANT:
        logger.info(f"⏭️  SKIPPING - USE_AI_ASSISTANT is False")
        print(f"⏭️  SKIPPING - USE_AI_ASSISTANT is False")
        return
    
    # Check if this session already has a Docker container running
    if session_id in state.session_docker_containers and state.session_docker_containers[session_id]:
        logger.info(f"⏭️  SKIPPING - Docker already running for session {session_id}")
        print(f"⏭️  SKIPPING - Docker already running for session {session_id}")
        return

    logger.info(f"🔄 STARTING SERVICES - Calling start_ai_assistant_agent")
    print(f"🔄 STARTING SERVICES - Calling start_ai_assistant_agent")
    
    await start_ai_assistant_agent(user_id=user_id, session_id=session_id)
    state.session_docker_containers[session_id] = True
    state.last_user_id = user_id
    
    logger.info(f"⏳ WAITING 2 seconds for Docker to initialize...")
    print(f"⏳ WAITING 2 seconds for Docker to initialize...")
    await asyncio.sleep(2)
    
    logger.info(f"📡 INITIALIZING MQTT CLIENT for session {session_id}")
    print(f"📡 INITIALIZING MQTT CLIENT for session {session_id}")
    mqtt_client = initialize_mqtt_client()
    if not mqtt_client:
        raise HTTPException(status_code=503, detail="MQTT client failed to initialize")
    state.session_mqtt_clients[session_id] = mqtt_client
    
    logger.info(f"✅ SERVICES STARTED - Session {session_id} ready!")
    print(f"✅ SERVICES STARTED - Session {session_id} ready!")


async def shutdown_services_if_idle(session_id: str, user_id: str) -> bool:
    """Stop the AI Assistant via REST APIs for a specific session immediately."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔌 SHUTDOWN_SERVICES - Session ID: {session_id}, User ID: {user_id}")
    print(f"🔌 SHUTDOWN_SERVICES - Session ID: {session_id}, User ID: {user_id}")
    
    # Disconnect MQTT client for this session
    if session_id in state.session_mqtt_clients:
        logger.info(f"📡 DISCONNECTING MQTT CLIENT for session {session_id}")
        print(f"📡 DISCONNECTING MQTT CLIENT for session {session_id}")
        state.session_mqtt_clients[session_id].disconnect()
        del state.session_mqtt_clients[session_id]
    
    # Stop Docker container for this session
    if session_id in state.session_docker_containers and state.session_docker_containers[session_id]:
        logger.info(f"🔄 STOPPING DOCKER - Calling kill_ai_assistant_agent")
        print(f"🔄 STOPPING DOCKER - Calling kill_ai_assistant_agent")
        await kill_ai_assistant_agent(user_id=user_id, session_id=session_id)
        del state.session_docker_containers[session_id]
        logger.info(f"✅ SERVICES STOPPED for session {session_id}")
        print(f"✅ SERVICES STOPPED for session {session_id}")
        return True
    
    logger.info(f"⏭️  NO SERVICES TO STOP for session {session_id}")
    print(f"⏭️  NO SERVICES TO STOP for session {session_id}")
    return False


async def ensure_services_ready(user_id: str, session_id: str) -> None:
    """Ensure REST-backed services are running for a specific session before handling a request."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 ENSURE_SERVICES_READY - Session ID: {session_id}, User ID: {user_id}")
    print(f"🔍 ENSURE_SERVICES_READY - Session ID: {session_id}, User ID: {user_id}")
    
    if not USE_AI_ASSISTANT:
        logger.info(f"⏭️  SKIPPING - USE_AI_ASSISTANT is False")
        print(f"⏭️  SKIPPING - USE_AI_ASSISTANT is False")
        return

    # Check if this session's Docker container is running
    if session_id not in state.session_docker_containers or not state.session_docker_containers[session_id]:
        logger.info(f"🔄 STARTING DOCKER - Calling start_ai_assistant_agent")
        print(f"🔄 STARTING DOCKER - Calling start_ai_assistant_agent")
        await start_ai_assistant_agent(user_id=user_id, session_id=session_id)
        state.session_docker_containers[session_id] = True
        state.last_user_id = user_id

    # Check if this session has an MQTT client
    if session_id not in state.session_mqtt_clients:
        logger.info(f"📡 INITIALIZING MQTT CLIENT for session {session_id}")
        print(f"📡 INITIALIZING MQTT CLIENT for session {session_id}")
        mqtt_client = initialize_mqtt_client()
        if not mqtt_client:
            raise HTTPException(status_code=503, detail="MQTT client failed to initialize")
        state.session_mqtt_clients[session_id] = mqtt_client
    
    logger.info(f"✅ SERVICES READY for session {session_id}")
    print(f"✅ SERVICES READY for session {session_id}")


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
