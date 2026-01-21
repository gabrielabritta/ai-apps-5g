"""Shared runtime state for the FastAPI server."""
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .mqtt_manager import MQTTClientManager

active_sessions: Dict[str, Dict[str, Any]] = {}
docker_container_running = False
mqtt_client_manager: Optional["MQTTClientManager"] = None
last_user_id: Optional[str] = None
