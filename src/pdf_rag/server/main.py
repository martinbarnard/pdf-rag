"""FastAPI server entry point for the pdf-rag visualisation interface."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# Path where the built React frontend will live
_STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path: Path | None = None, ingest_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_path: Path to the kuzu database. Defaults to DEFAULT_DB_PATH.
        ingest_dir: Destination folder for uploaded documents. Defaults to DEFAULT_INGEST_DIR.
    """
    from pdf_rag.config import DEFAULT_DB_PATH, DEFAULT_INGEST_DIR
    resolved_db = db_path or DEFAULT_DB_PATH
    resolved_ingest_dir = ingest_dir or DEFAULT_INGEST_DIR
    resolved_ingest_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="pdf-rag",
        description="Graph-RAG visualisation server for scientific papers.",
        version="0.1.0",
    )

    # Stash paths in app state so routers can access them
    app.state.db_path = resolved_db
    app.state.ingest_dir = resolved_ingest_dir

    # CORS — allow local Vite dev server and any localhost origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Convenience redirects
    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/app/")

    @app.get("/app", include_in_schema=False)
    async def app_redirect() -> RedirectResponse:
        return RedirectResponse(url="/app/")

    # Health check
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    # Register API routers
    from pdf_rag.server.routers import graph, ingest, search
    app.include_router(graph.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")

    # Serve built frontend assets (JS/CSS/images)
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/app/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    # Catch-all: any /app/* path that isn't a real asset returns index.html
    # so React Router handles client-side navigation on hard refresh.
    _index = _STATIC_DIR / "index.html"

    @app.get("/app/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        return FileResponse(str(_index))

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
