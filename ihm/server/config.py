"""Configuration utilities for the FastAPI server."""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from config file in the same directory as this file
config_file = Path(__file__).parent / "config.env"
load_dotenv(config_file)
print(f"🔧 Loading config from: {config_file}")
print(f"🔧 Config file exists: {config_file.exists()}")

# Add project root directory to path (for potential imports)
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in os.sys.path:
    os.sys.path.append(str(project_root))

DEFAULT_HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("PORT", 8000))
MQTT_BROKER = os.getenv("MQTT_BROKER", "0.0.0.0")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_INPUT_TOPIC = os.getenv("MQTT_INPUT_TOPIC", "input")
MQTT_OUTPUT_TOPIC = os.getenv("MQTT_OUTPUT_TOPIC", "output")
INFERENCE_MODEL_NAME = os.getenv("INFERENCE_MODEL", "gemma3:27b")
USE_AI_ASSISTANT = os.getenv("USE_AI_ASSISTANT", "false").lower() == "true"

print(f"🔧 USE_AI_ASSISTANT env value: '{os.getenv('USE_AI_ASSISTANT', 'NOT_SET')}'")
print(f"🔧 USE_AI_ASSISTANT parsed to: {USE_AI_ASSISTANT}")
AI_ASSISTANT_START_API_URL = os.getenv(
    "AI_ASSISTANT_START_API_URL",
    "http://localhost:8002/ai_assistant/start_docker",
)
AI_ASSISTANT_KILL_API_URL = os.getenv(
    "AI_ASSISTANT_KILL_API_URL",
    "http://localhost:8001/ai_assistant/kill_docker",
)

print(f"🔧 AI_ASSISTANT_START_API_URL: {AI_ASSISTANT_START_API_URL}")
print(f"🔧 AI_ASSISTANT_KILL_API_URL: {AI_ASSISTANT_KILL_API_URL}")
print(f"🔧 MQTT_BROKER: {MQTT_BROKER}:{MQTT_PORT}")
print(f"🔧 INFERENCE_MODEL: {INFERENCE_MODEL_NAME}")
print("="*80)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
