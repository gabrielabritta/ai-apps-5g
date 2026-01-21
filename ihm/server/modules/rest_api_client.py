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


async def start_ai_assistant_agent(user_id: str, session_id: str) -> None:
    """Request the REST API to start the AI Assistant container for a specific session."""
    payload: Dict[str, Any] = {
        "broker": MQTT_BROKER,
        "port": MQTT_PORT,
        "user_id": _coerce_user_id(user_id),
        "session_id": session_id,
        "input_topic": MQTT_INPUT_TOPIC,
        "output_topic": MQTT_OUTPUT_TOPIC,
        "inference_model_name": INFERENCE_MODEL_NAME,
    }

    logger.info(
        f"🚀 CALLING REST API - START DOCKER\n"
        f"  URL: {AI_ASSISTANT_START_API_URL}\n"
        f"  Session ID: {session_id}\n"
        f"  User ID: {user_id} (coerced to {_coerce_user_id(user_id)})\n"
        f"  Payload: {payload}"
    )
    print(
        f"🚀 CALLING REST API - START DOCKER\n"
        f"  URL: {AI_ASSISTANT_START_API_URL}\n"
        f"  Session ID: {session_id}\n"
        f"  User ID: {user_id} (coerced to {_coerce_user_id(user_id)})\n"
        f"  Payload: {payload}"
    )

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(AI_ASSISTANT_START_API_URL, json=payload)

    if response.status_code != 200:
        logger.error(f"❌ REST API START FAILED - Status: {response.status_code}, Response: {response.text}")
        print(f"❌ REST API START FAILED - Status: {response.status_code}, Response: {response.text}")
        raise HTTPException(
            status_code=503,
            detail="AI Assistant REST API failed to start the container",
        )
    
    logger.info(f"✅ REST API START SUCCESS - Session ID: {session_id}")
    print(f"✅ REST API START SUCCESS - Session ID: {session_id}")


async def kill_ai_assistant_agent(user_id: str, session_id: str) -> None:
    """Request the REST API to stop the AI Assistant container for a specific session."""
    payload = {
        "user_id": _coerce_user_id(user_id),
        "session_id": session_id,
    }

    logger.info(
        f"🛑 CALLING REST API - KILL DOCKER\n"
        f"  URL: {AI_ASSISTANT_KILL_API_URL}\n"
        f"  Session ID: {session_id}\n"
        f"  User ID: {user_id} (coerced to {_coerce_user_id(user_id)})\n"
        f"  Payload: {payload}"
    )
    print(
        f"🛑 CALLING REST API - KILL DOCKER\n"
        f"  URL: {AI_ASSISTANT_KILL_API_URL}\n"
        f"  Session ID: {session_id}\n"
        f"  User ID: {user_id} (coerced to {_coerce_user_id(user_id)})\n"
        f"  Payload: {payload}"
    )

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(AI_ASSISTANT_KILL_API_URL, json=payload)

    if response.status_code != 200:
        logger.error(f"❌ REST API KILL FAILED - Status: {response.status_code}, Response: {response.text}")
        print(f"❌ REST API KILL FAILED - Status: {response.status_code}, Response: {response.text}")
        raise HTTPException(
            status_code=503,
            detail="AI Assistant REST API failed to stop the container",
        )
    
    logger.info(f"✅ REST API KILL SUCCESS - Session ID: {session_id}")
    print(f"✅ REST API KILL SUCCESS - Session ID: {session_id}")
