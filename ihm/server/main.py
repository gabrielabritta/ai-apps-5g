"""FastAPI server for AI Assistant integration."""
import asyncio
import contextlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from ihm.server.config import DEFAULT_HOST, DEFAULT_PORT, USE_AI_ASSISTANT
from ihm.server.docker_manager import (
    check_docker_container_status,
    monitor_docker_container,
    start_docker_container,
    stop_docker_container,
)
from ihm.server.models import HealthResponse, InferenceRequest, ServiceRequest, ServiceResponse
from ihm.server.mqtt_manager import initialize_mqtt_client
from ihm.server import state

logger = logging.getLogger(__name__)


@asynccontextmanager
def lifespan(app: FastAPI):
    """Start background resources and clean them up when the server stops."""
    if USE_AI_ASSISTANT:
        state.container_monitor_task = asyncio.create_task(monitor_docker_container())
    try:
        yield
    finally:
        if state.container_monitor_task:
            state.container_monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.container_monitor_task
        if state.mqtt_client_manager:
            state.mqtt_client_manager.disconnect()
            state.mqtt_client_manager = None
        if state.docker_container_running:
            stop_docker_container()


app = FastAPI(
    title="AI Assistant API",
    description="API for AI Assistant integration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """Root endpoint to verify if the server is working."""
    return HealthResponse(status="ok", message="AI Assistant API is working!")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    if USE_AI_ASSISTANT and state.docker_container_running and state.mqtt_client_manager and state.mqtt_client_manager.connected:
        return HealthResponse(status="healthy", message="AI Assistant Docker container is running and MQTT connected")
    if USE_AI_ASSISTANT:
        return HealthResponse(status="warning", message="AI Assistant enabled but Docker container or MQTT not ready")
    return HealthResponse(status="healthy", message="Server working in mock mode")


@app.post("/turn_on_services", response_model=ServiceResponse)
async def turn_on_services(request: ServiceRequest) -> ServiceResponse:
    """Register a new active session and start services when necessary."""
    state.active_sessions[request.session_id] = {"user_id": request.user_id}
    active_count = len(state.active_sessions)

    if USE_AI_ASSISTANT and active_count == 1 and not state.docker_container_running:
        started = start_docker_container(user_id=request.user_id)
        if started:
            await asyncio.sleep(2)
            if not initialize_mqtt_client():
                raise HTTPException(status_code=503, detail="MQTT client failed to initialize")
        else:
            raise HTTPException(status_code=503, detail="AI Assistant agent container failed to start")

    return ServiceResponse(
        status="ok",
        message="Services ready",
        active_sessions_count=active_count,
    )


@app.post("/turn_off_services")
async def turn_off_services(request: Request) -> Dict[str, str]:
    """Remove the session and stop services if no sessions remain."""
    data: Dict[str, str] = {}
    body = await request.body()
    if body:
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid request body: {exc}")

    session_id = data.get("session_id", "")
    if not session_id:
        raise HTTPException(status_code=400, detail="No session_id provided")

    state.active_sessions.pop(session_id, None)
    active_count = len(state.active_sessions)

    if active_count == 0:
        if state.mqtt_client_manager:
            state.mqtt_client_manager.disconnect()
            state.mqtt_client_manager = None
        if state.docker_container_running:
            stop_docker_container()
        return {"status": "ok", "message": "Services turned off - no active sessions", "active_sessions_count": "0"}

    return {
        "status": "ok",
        "message": f"Session removed, services remain active - {active_count} active session(s)",
        "active_sessions_count": str(active_count),
    }


@app.post("/inference")
async def run_inference(request: InferenceRequest):
    """Inference endpoint that returns SSE streaming response."""
    if USE_AI_ASSISTANT:
        await ensure_services_ready()
        mqtt_message = {
            "query": request.query,
            "search_db": request.search_db,
            "search_urls": request.search_urls,
            "use_history": request.use_history,
            "n_chunks": request.n_chunks,
        }
        mqtt_task = asyncio.create_task(
            state.mqtt_client_manager.publish_and_wait(mqtt_message, timeout=600)
        )
        generator = build_sse_stream(mqtt_task)
    else:
        generator = build_mock_stream(request.query)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def ensure_services_ready() -> None:
    """Ensure Docker and MQTT services are running before handling a request."""
    is_running, _ = check_docker_container_status()
    if not is_running:
        state.docker_container_running = False
        user_id = next(iter(state.active_sessions.values()), {}).get("user_id", "1")
        if not start_docker_container(user_id=user_id):
            raise HTTPException(status_code=503, detail="AI Assistant agent Docker container failed to start")
        await asyncio.sleep(5)
        is_running, _ = check_docker_container_status()
        if not is_running:
            raise HTTPException(status_code=503, detail="AI Assistant agent Docker container failed to start")
    state.docker_container_running = True

    if not initialize_mqtt_client():
        raise HTTPException(status_code=503, detail="MQTT client failed to initialize")


async def build_sse_stream(mqtt_task: asyncio.Task):
    """Yield SSE events while waiting for the MQTT response."""
    message_id = f"ai-{id(mqtt_task)}"
    yield format_sse_event({"type": "start-step"})
    yield format_sse_event({"type": "text-start", "id": message_id})

    while not mqtt_task.done():
        await asyncio.sleep(1)
        yield ": heartbeat\n\n"

    response = await mqtt_task
    answer_text = response.get("response", "") if isinstance(response, dict) else str(response)
    for word in answer_text.split():
        yield format_sse_event({"type": "text-delta", "id": message_id, "delta": f"{word} "})
        await asyncio.sleep(0.05)

    yield format_sse_event({"type": "text-end", "id": message_id})
    yield format_sse_event({"type": "finish-step"})
    yield format_sse_event({"type": "finish"})
    yield "data: [DONE]\n\n"


async def build_mock_stream(query: str):
    """Generate a short mock streaming response when the assistant is disabled."""
    message_id = f"mock-{hash(query)}"
    yield format_sse_event({"type": "start-step"})
    yield format_sse_event({"type": "text-start", "id": message_id})

    for word in "This is an example response from the mock server.".split():
        yield format_sse_event({"type": "text-delta", "id": message_id, "delta": f"{word} "})
        await asyncio.sleep(0.05)

    yield format_sse_event({"type": "text-end", "id": message_id})
    yield format_sse_event({"type": "finish-step"})
    yield format_sse_event({"type": "finish"})
    yield "data: [DONE]\n\n"


def format_sse_event(payload: Dict[str, str]) -> str:
    """Format a dictionary as an SSE data event."""
    return f"data: {json.dumps(payload)}\n\n"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "ihm.server.main:app",
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        reload=True,
    )
