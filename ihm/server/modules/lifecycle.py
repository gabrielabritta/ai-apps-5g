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
        # Clean up MQTT clients for all users
        for user_id, mqtt_client in list(state.user_mqtt_clients.items()):
            mqtt_client.disconnect()
        state.user_mqtt_clients.clear()
        
        # Stop Docker containers for all users
        if USE_AI_ASSISTANT:
            for user_id in list(state.user_docker_containers.keys()):
                await kill_ai_assistant_agent(user_id=user_id)
            state.user_docker_containers.clear()
        
        # Clean up deprecated global variables
        if state.mqtt_client_manager:
            state.mqtt_client_manager.disconnect()
            state.mqtt_client_manager = None
        state.docker_container_running = False
