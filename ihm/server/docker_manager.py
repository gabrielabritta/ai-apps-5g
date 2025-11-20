"""Docker helpers used by the FastAPI server."""

import asyncio
import json
import logging
import subprocess
from typing import Optional, Tuple

from ihm.server import state

logger = logging.getLogger(__name__)


def check_docker_container_status() -> Tuple[bool, Optional[str]]:
    """Check current status of the configured Docker container."""
    try:
        running_result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={state.docker_container_name}",
                "--format",
                "{{.ID}}|{{.Names}}|{{.Status}}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if state.docker_container_name in running_result.stdout:
            for line in running_result.stdout.strip().split("\n"):
                if state.docker_container_name in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        return True, parts[0]
            return True, None

        stopped_result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={state.docker_container_name}",
                "--format",
                "{{.ID}}|{{.Names}}|{{.Status}}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if state.docker_container_name in stopped_result.stdout:
            for line in stopped_result.stdout.strip().split("\n"):
                if state.docker_container_name in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        return False, parts[0]
            return False, None

        return False, None
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error while checking Docker container status: %s", exc)
        return False, None


async def monitor_docker_container():
    """Monitor the Docker container to detect unexpected stops."""
    consecutive_failures = 0

    while True:
        try:
            await asyncio.sleep(5)
            if not state.docker_container_running:
                consecutive_failures = 0
                continue

            is_running, container_id = check_docker_container_status()
            if is_running:
                consecutive_failures = 0
                continue

            consecutive_failures += 1
            state.docker_container_running = False
            if container_id:
                log_container_failure(container_id)
            if consecutive_failures >= 3:
                break
        except asyncio.CancelledError:
            break
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error monitoring Docker container: %s", exc)
            await asyncio.sleep(5)


def log_container_failure(container_id: str) -> None:
    """Log details about a failed container for quick debugging."""
    try:
        result_logs = subprocess.run(
            ["docker", "logs", container_id], capture_output=True, text=True, check=False
        )
        if result_logs.stdout:
            logger.warning("Container logs (tail): %s", result_logs.stdout[-500:])
        if result_logs.stderr:
            logger.warning("Container errors (tail): %s", result_logs.stderr[-500:])

        result_inspect = subprocess.run(
            ["docker", "inspect", container_id, "--format", "{{.State.ExitCode}}|{{.State.Error}}|{{.State.FinishedAt}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result_inspect.stdout:
            parts = result_inspect.stdout.strip().split("|")
            if len(parts) >= 3:
                logger.warning(
                    "Container exit info - exit code: %s, error: %s, finished at: %s",
                    parts[0],
                    parts[1],
                    parts[2],
                )

        result_status = subprocess.run(
            ["docker", "inspect", container_id, "--format", "{{json .State}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result_status.stdout:
            try:
                state_json = json.loads(result_status.stdout)
                logger.warning("Container state: %s", json.dumps(state_json))
            except json.JSONDecodeError:
                logger.warning("Raw container state: %s", result_status.stdout)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to log container failure: %s", exc)


def start_docker_container(user_id: str = "1") -> bool:
    """Start the AI assistant Docker container when services are needed."""
    try:
        user_id_int = int(user_id)
    except ValueError:
        user_id_int = abs(hash(user_id)) % (10**8)

    try:
        running_check = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={state.docker_container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if state.docker_container_name in running_check.stdout:
            state.docker_container_running = True
            return True

        stopped_check = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={state.docker_container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if state.docker_container_name in stopped_check.stdout:
            subprocess.run(
                ["docker", "rm", state.docker_container_name], capture_output=True, text=True, check=False
            )

        command = [
            "docker",
            "run",
            "-d",
            "--name",
            state.docker_container_name,
            "-p",
            "1883:1883",
            "ai_assistant_image",
            str(user_id_int),
        ]
        subprocess.run(command, capture_output=True, text=True, check=True)
        state.docker_container_running = True
        return True
    except subprocess.CalledProcessError as exc:  # pragma: no cover - docker errors
        logger.exception("Docker command failed: %s", exc)
        state.docker_container_running = False
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error starting Docker container: %s", exc)
        state.docker_container_running = False
        return False


def stop_docker_container() -> bool:
    """Stop the AI assistant Docker container when not needed."""
    if not state.docker_container_running:
        return True

    try:
        subprocess.run(
            ["docker", "stop", state.docker_container_name],
            capture_output=True,
            text=True,
            check=True,
        )
        state.docker_container_running = False
        return True
    except subprocess.CalledProcessError as exc:  # pragma: no cover - docker errors
        logger.warning("Container stop returned an error: %s", exc)
        state.docker_container_running = False
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to stop Docker container: %s", exc)
        return False
