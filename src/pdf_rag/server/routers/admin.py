"""Admin/maintenance API endpoints."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["admin"], prefix="/admin")


def _store(request: Request):
    from pdf_rag.graph.store import GraphStore
    return GraphStore(request.app.state.db_path)


@router.get("/stats")
async def db_stats(request: Request) -> dict:
    """Current node counts and DB file size."""
    store = _store(request)
    counts = {}
    for label in ("Paper", "Author", "Topic", "Chunk", "Institution", "Venue"):
        r = store.execute(f"MATCH (n:{label}) RETURN count(n)")
        counts[label.lower() + "s"] = r.get_next()[0]

    db_path: Path = request.app.state.db_path
    size_bytes = db_path.stat().st_size if db_path.exists() else 0
    return {"counts": counts, "db_path": str(db_path), "size_bytes": size_bytes}


@router.post("/truncate")
async def truncate_db(request: Request) -> dict:
    """Delete all data from the graph database but keep the schema.

    Edges must be dropped before nodes (referential integrity).
    """
    store = _store(request)

    edge_tables = [
        "AUTHORED", "AFFILIATED_WITH", "PUBLISHED_IN", "DISCUSSES",
        "CITES", "HAS_CHUNK", "MENTIONS_TOPIC", "MENTIONS_AUTHOR", "RELATED_TO",
    ]
    node_tables = ["Paper", "Author", "Institution", "Venue", "Topic", "Chunk"]

    for table in edge_tables:
        try:
            store.execute(f"MATCH ()-[r:{table}]->() DELETE r")
        except Exception:
            pass  # table may be empty or not exist yet

    for table in node_tables:
        try:
            store.execute(f"MATCH (n:{table}) DELETE n")
        except Exception:
            pass

    return {"status": "truncated"}


@router.delete("/db")
async def delete_db(request: Request) -> dict:
    """Delete the kuzu database file entirely.

    The server will recreate an empty database on the next request.
    Note: the current in-memory connection will be stale after this —
    restart the server for a fully clean state.
    """
    db_path: Path = request.app.state.db_path

    if db_path.exists():
        if db_path.is_dir():
            shutil.rmtree(db_path)
        else:
            db_path.unlink()

    return {"status": "deleted", "path": str(db_path)}
