"""FastAPI application factory and middleware setup."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ihm.server.modules.api import router as api_router
from ihm.server.config import DEFAULT_HOST, DEFAULT_PORT
from ihm.server.modules.lifecycle import lifespan


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
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
    app.include_router(api_router)
    return app


app = create_app()


__all__ = ["app", "DEFAULT_HOST", "DEFAULT_PORT", "create_app"]
