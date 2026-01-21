"""API routes for the AI Assistant server."""
import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """Return a simple response to confirm the server is alive."""
    return HealthResponse(status="ok", message="AI Assistant API is working!")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Report service health for Docker and MQTT dependencies."""
    if USE_AI_ASSISTANT:
        active_containers = len(state.session_docker_containers)
        active_mqtt_clients = len(state.session_mqtt_clients)
        
        if active_containers > 0 and active_mqtt_clients > 0:
            return HealthResponse(
                status="healthy",
                message=f"AI Assistant running for {active_containers} session(s) with {active_mqtt_clients} MQTT client(s)",
            )
        if active_containers > 0 or active_mqtt_clients > 0:
            return HealthResponse(
                status="warning",
                message=f"AI Assistant partially ready: {active_containers} container(s), {active_mqtt_clients} MQTT client(s)",
            )
        return HealthResponse(
            status="healthy",
            message="AI Assistant enabled but no active sessions",
        )
    return HealthResponse(status="healthy", message="Server working in mock mode")


@router.post("/turn_on_services", response_model=ServiceResponse)
async def turn_on_services(request: ServiceRequest) -> ServiceResponse:
    """Register a session and start services (Docker + MQTT) for this session."""
    state.active_sessions[request.session_id] = {"user_id": request.user_id}
    state.last_user_id = request.user_id
    active_count = len(state.active_sessions)
    
    # Count sessions for this specific user
    user_session_count = sum(
        1 for session_data in state.active_sessions.values() 
        if session_data.get("user_id") == request.user_id
    )
    
    # Log when someone enters the app
    logger.info(
        f"🔵 SESSION STARTED - User ID: {request.user_id}, "
        f"Session ID: {request.session_id}, "
        f"Total Active Sessions: {active_count}, "
        f"User Sessions: {user_session_count}"
    )
    print(
        f"🔵 SESSION STARTED - User ID: {request.user_id}, "
        f"Session ID: {request.session_id}, "
        f"Total Active Sessions: {active_count}, "
        f"User Sessions: {user_session_count}"
    )
    
    await start_services_if_needed(user_id=request.user_id, session_id=request.session_id)
    return ServiceResponse(
        status="ok",
        message=f"Services started for session {request.session_id}",
        active_sessions_count=active_count,
    )


@router.post("/turn_off_services")
async def turn_off_services(request: Request) -> Dict[str, str]:
    """Remove a session and immediately stop services (Docker + MQTT) for this session."""
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
    
    # Count remaining sessions for this specific user
    user_session_count = sum(
        1 for session_data in state.active_sessions.values() 
        if session_data.get("user_id") == user_id
    )
    
    # Log when someone closes the app (tab/guide)
    logger.info(
        f"🔴 SESSION ENDED - User ID: {user_id}, "
        f"Session ID: {session_id}, "
        f"Total Remaining Sessions: {active_count}, "
        f"User Remaining Sessions: {user_session_count}"
    )
    print(
        f"🔴 SESSION ENDED - User ID: {user_id}, "
        f"Session ID: {session_id}, "
        f"Total Remaining Sessions: {active_count}, "
        f"User Remaining Sessions: {user_session_count}"
    )
    
    services_shutdown = await shutdown_services_if_idle(session_id=session_id, user_id=user_id)
    
    if services_shutdown:
        return {
            "status": "ok",
            "message": f"Services stopped for session {session_id}",
            "active_sessions_count": str(active_count),
            "user_sessions_count": str(user_session_count),
        }

    return {
        "status": "ok",
        "message": f"Session {session_id} removed (services were not running)",
        "active_sessions_count": str(active_count),
        "user_sessions_count": str(user_session_count),
    }


@router.post("/inference")
async def run_inference(request: InferenceRequest):
    """Stream inference responses as Server-Sent Events (SSE)."""
    if USE_AI_ASSISTANT:
        await ensure_services_ready(user_id=request.user_id, session_id=request.session_id)
        mqtt_message = {
            "query": request.query,
            "search_db": request.search_db,
            "search_urls": request.search_urls,
            "use_history": request.use_history,
            "n_chunks": request.n_chunks,
        }
        # Get the MQTT client for this specific session
        mqtt_client = state.session_mqtt_clients.get(request.session_id)
        if not mqtt_client:
            raise HTTPException(
                status_code=503, 
                detail=f"MQTT client not available for session {request.session_id}"
            )
        mqtt_task = asyncio.create_task(
            mqtt_client.publish_and_wait(mqtt_message, timeout=600)
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
