"""Ingestion trigger API endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile

router = APIRouter(tags=["ingest"])

_ALLOWED_SUFFIXES = {".pdf", ".docx", ".md", ".html", ".htm", ".tex"}


@router.post("/ingest")
async def ingest_file(file: UploadFile, request: Request) -> dict:
    """Upload and ingest a single document into the graph database.

    Returns chunk_count, entity_count, and citation_count on success.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix!r}")

    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from pdf_rag.pipeline import ingest_document
        result = ingest_document(tmp_path, db_path=request.app.state.db_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "paper_id": result.paper_id,
        "chunk_count": result.chunk_count,
        "entity_count": result.entity_count,
        "citation_count": result.citation_count,
    }
