#!/usr/bin/env python3
from flask import Flask, request, jsonify
from pydantic import ValidationError, Extra
import subprocess
from common import AiAssistantKillData, generate_docker_name


app = Flask(__name__)


@app.route("/ai_assistant/kill_docker", methods=["POST"])
def kill_ai_assistant_agent_docker():
    """Kills an AiAssistant agent inside a Docker container based on the provided input data."""
    print("\n" + "="*80)
    print("🛑 REST API CALLED - KILL DOCKER")
    print("="*80)
    
    data = request.get_json(silent=True)
    if data is None:
        print("❌ ERROR: Malformed JSON")
        return jsonify({"error": "Malformed JSON"}), 400

    print(f"📦 Received data: {data}")

    # Validate input data
    try:
        input_data = AiAssistantKillData(**data)
        print(f"✅ Data validated successfully")
        print(f"   - User ID: {input_data.user_id}")
        print(f"   - Session ID: {input_data.session_id}")
    except ValidationError as e:
        print(f"❌ VALIDATION ERROR: {e.errors()}")
        return jsonify({"error": "Invalid input data", "details": e.errors()}), 400

    # Create a name for the Docker container with the session id
    container_name = generate_docker_name(input_data.session_id)
    print(f"🐳 Container name: {container_name}")

    # Call the docker with the provided parameters
    try:
        print(f"🔧 Stopping Docker container...")
        command = [
            "docker", "stop", container_name
        ]
        result_stop = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"   ✅ Container stopped: {result_stop.stdout.strip()}")
        
        print(f"🔧 Removing Docker container...")
        command = [
            "docker", "rm", container_name
        ]
        result_rm = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"   ✅ Container removed: {result_rm.stdout.strip()}")
        print("="*80 + "\n")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ DOCKER ERROR: {e.stderr}")
        print("="*80 + "\n")
        return jsonify({"error": "Failed to kill Docker container", "details": e.stderr}), 500

    return jsonify({"message": "Docker container killed successfully",
                    "output_stop": result_stop.stdout,
                    "output_rm": result_rm.stdout}), 200



if __name__ == "__main__":
    # listen on all interfaces so it's reachable from containers/other hosts
    app.run(host="0.0.0.0", port=8001, debug=False)
