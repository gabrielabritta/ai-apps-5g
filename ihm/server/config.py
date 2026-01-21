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
DEFAULT_HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("PORT", 8000))
MQTT_BROKER = os.getenv("MQTT_BROKER", "0.0.0.0")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_INPUT_TOPIC = os.getenv("MQTT_INPUT_TOPIC", "input")
MQTT_OUTPUT_TOPIC = os.getenv("MQTT_OUTPUT_TOPIC", "output")
INFERENCE_MODEL_NAME = os.getenv("INFERENCE_MODEL", "gemma3:27b")
AI_ASSISTANT_START_API_URL = os.getenv(
    "AI_ASSISTANT_START_API_URL",
    "http://localhost:8002/ai_assistant/start_docker",
)
AI_ASSISTANT_KILL_API_URL = os.getenv(
    "AI_ASSISTANT_KILL_API_URL",
    "http://localhost:8001/ai_assistant/kill_docker",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
