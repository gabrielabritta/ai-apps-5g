"""Shared runtime state for the FastAPI server."""
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .modules.mqtt_manager import MQTTClientManager

# Maps session_id -> {"user_id": str}
active_sessions: Dict[str, Dict[str, Any]] = {}

# Maps session_id -> True (tracks which sessions have Docker containers running)
session_docker_containers: Dict[str, bool] = {}

# Maps session_id -> MQTTClientManager (each session has their own MQTT client)
session_mqtt_clients: Dict[str, "MQTTClientManager"] = {}

# Deprecated: kept for backward compatibility, will be removed
docker_container_running = False
mqtt_client_manager: Optional["MQTTClientManager"] = None
last_user_id: Optional[str] = None
user_docker_containers: Dict[str, bool] = {}  # Deprecated
user_mqtt_clients: Dict[str, "MQTTClientManager"] = {}  # Deprecated
