"""Shared runtime state for the FastAPI server."""
import asyncio
from typing import Any, Dict, Optional, TYPE_CHECKING
from ihm.server.config import DOCKER_CONTAINER_NAME

if TYPE_CHECKING:  # pragma: no cover
    from .mqtt_manager import MQTTClientManager

active_sessions: Dict[str, Dict[str, Any]] = {}
docker_container_running = False
container_monitor_task: Optional[asyncio.Task] = None
mqtt_client_manager: Optional["MQTTClientManager"] = None
docker_container_name = DOCKER_CONTAINER_NAME
