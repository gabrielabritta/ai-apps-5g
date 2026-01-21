#!/usr/bin/env python3
from flask import Flask, request, jsonify
from pydantic import ValidationError, Extra
import subprocess
from common import AiAssistantInputData, generate_docker_name


app = Flask(__name__)


@app.route("/ai_assistant/start_docker", methods=["POST"])
def start_ai_assistant_agent_docker():
    """Starts an AiAssistant agent inside a Docker container based on the provided input data."""
    print("\n" + "="*80)
    print("🚀 REST API CALLED - START DOCKER")
    print("="*80)
    
    data = request.get_json(silent=True)
    if data is None:
        print("❌ ERROR: Malformed JSON")
        return jsonify({"error": "Malformed JSON"}), 400

    print(f"📦 Received data: {data}")

    # Validate input data
    try:
        input_data = AiAssistantInputData(**data)
        print(f"✅ Data validated successfully")
        print(f"   - User ID: {input_data.user_id}")
        print(f"   - Session ID: {input_data.session_id}")
        print(f"   - Broker: {input_data.broker}:{input_data.port}")
        print(f"   - Topics: IN={input_data.input_topic}, OUT={input_data.output_topic}")
        print(f"   - Model: {input_data.inference_model_name}")
    except ValidationError as e:
        print(f"❌ VALIDATION ERROR: {e.errors()}")
        return jsonify({"error": "Invalid input data", "details": e.errors()}), 400

    # Create a name for the Docker container with the session id
    container_name = generate_docker_name(input_data.session_id)
    print(f"🐳 Container name: {container_name}")

    # Call the docker with the provided parameters
    try:
        command = [
            "docker", "run", "-d", "--network=host",
            "--name", container_name,
            "ai_assistant_image",
            f"--broker={input_data.broker}",
            f"--port={input_data.port}",
            f"--user_id={input_data.user_id}",
            f"--input_topic={input_data.input_topic}",
            f"--output_topic={input_data.output_topic}",
            f"--inference_model_name={input_data.inference_model_name}"
        ]
        
        print(f"🔧 Executing Docker command:")
        print(f"   {' '.join(command)}")
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"✅ Docker container started successfully!")
        print(f"   Container ID: {result.stdout.strip()}")
        print("="*80 + "\n")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ DOCKER ERROR: {e.stderr}")
        print("="*80 + "\n")
        return jsonify({"error": "Failed to start Docker container", "details": e.stderr}), 500

    return jsonify({"message": "Docker container started successfully", "output": result.stdout}), 200


if __name__ == "__main__":
    # listen on all interfaces so it's reachable from containers/other hosts
    app.run(host="0.0.0.0", port=8002, debug=False)
