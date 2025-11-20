"""Configuration utilities for the FastAPI server."""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from config file
load_dotenv("config.env")

# Add project root directory to path (for potential imports)
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in os.sys.path:
    os.sys.path.append(str(project_root))

USE_AI_ASSISTANT = os.getenv("USE_AI_ASSISTANT", "false").lower() == "true"
DOCKER_CONTAINER_NAME = os.getenv("DOCKER_CONTAINER_NAME", "ai_assistant_agent")
DEFAULT_HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("PORT", 8000))
MQTT_BROKER = os.getenv("MQTT_BROKER", "0.0.0.0")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
