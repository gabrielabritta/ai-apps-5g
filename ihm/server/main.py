"""Entrypoint for running the FastAPI server."""
import uvicorn

from ihm.server.modules.app import DEFAULT_HOST, DEFAULT_PORT, app


if __name__ == "__main__":
    uvicorn.run(
        "ihm.server.modules.app:app",
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        reload=True,
    )
