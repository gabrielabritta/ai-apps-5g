"""Application lifespan management for background services."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ihm.server import state
from ihm.server.config import USE_AI_ASSISTANT
from ihm.server.modules.rest_api_client import kill_ai_assistant_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Clean up services when the FastAPI server stops."""
    try:
        yield
    finally:
        if state.mqtt_client_manager:
            state.mqtt_client_manager.disconnect()
            state.mqtt_client_manager = None
        if USE_AI_ASSISTANT and state.docker_container_running:
            user_id = state.last_user_id or "1"
            await kill_ai_assistant_agent(user_id=user_id)
            state.docker_container_running = False
