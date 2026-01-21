"""API routes for the AI Assistant server."""
import asyncio
import json
from typing import Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ihm.server import state
from ihm.server.config import USE_AI_ASSISTANT
from ihm.server.models import (
    HealthResponse,
    InferenceRequest,
    ServiceRequest,
    ServiceResponse,
)
from ihm.server.modules.services import (
    build_mock_stream,
    build_sse_stream,
    ensure_services_ready,
    shutdown_services_if_idle,
    start_services_if_needed,
)

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """Return a simple response to confirm the server is alive."""
    return HealthResponse(status="ok", message="AI Assistant API is working!")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Report service health for Docker and MQTT dependencies."""
    if (
        USE_AI_ASSISTANT
        and state.docker_container_running
        and state.mqtt_client_manager
        and state.mqtt_client_manager.connected
    ):
        return HealthResponse(
            status="healthy",
            message="AI Assistant Docker container is running and MQTT connected",
        )
    if USE_AI_ASSISTANT:
        return HealthResponse(
            status="warning",
            message="AI Assistant enabled but Docker container or MQTT not ready",
        )
    return HealthResponse(status="healthy", message="Server working in mock mode")


@router.post("/turn_on_services", response_model=ServiceResponse)
async def turn_on_services(request: ServiceRequest) -> ServiceResponse:
    """Register a session and start services when needed."""
    state.active_sessions[request.session_id] = {"user_id": request.user_id}
    state.last_user_id = request.user_id
    active_count = len(state.active_sessions)
    await start_services_if_needed(active_count=active_count, user_id=request.user_id)
    return ServiceResponse(
        status="ok",
        message="Services ready",
        active_sessions_count=active_count,
    )


@router.post("/turn_off_services")
async def turn_off_services(request: Request) -> Dict[str, str]:
    """Remove a session and stop services when no sessions remain."""
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

    session_data = state.active_sessions.pop(session_id, None)
    user_id = session_data.get("user_id") if session_data else state.last_user_id or "1"
    active_count = len(state.active_sessions)
    if await shutdown_services_if_idle(active_count=active_count, user_id=user_id):
        return {
            "status": "ok",
            "message": "Services turned off - no active sessions",
            "active_sessions_count": "0",
        }

    return {
        "status": "ok",
        "message": (
            "Session removed, services remain active - "
            f"{active_count} active session(s)"
        ),
        "active_sessions_count": str(active_count),
    }


@router.post("/inference")
async def run_inference(request: InferenceRequest):
    """Stream inference responses as Server-Sent Events (SSE)."""
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

__all__ = ["router"]
