"""FastAPI server entry point for the pdf-rag visualisation interface."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Path where the built React frontend will live
_STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_path: Path to the kuzu database. Defaults to DEFAULT_DB_PATH.
    """
    from pdf_rag.config import DEFAULT_DB_PATH
    resolved_db = db_path or DEFAULT_DB_PATH

    app = FastAPI(
        title="pdf-rag",
        description="Graph-RAG visualisation server for scientific papers.",
        version="0.1.0",
    )

    # Stash db_path in app state so routers can access it
    app.state.db_path = resolved_db

    # CORS — allow local Vite dev server and any localhost origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    # Register API routers
    from pdf_rag.server.routers import graph, ingest, search
    app.include_router(graph.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")

    # Serve built frontend — create dir if missing so mount doesn't fail
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/app", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

    return app


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Start the uvicorn server. Used as the pdf-rag-serve entry point."""
    import uvicorn
    uvicorn.run(
        "pdf_rag.server.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


# Allow `python -m pdf_rag.server.main` for quick start
if __name__ == "__main__":
    serve()
