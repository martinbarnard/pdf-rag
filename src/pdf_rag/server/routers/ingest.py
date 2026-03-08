"""Ingestion trigger API endpoints with background job queue."""

from __future__ import annotations

import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, UploadFile

router = APIRouter(tags=["ingest"])

_ALLOWED_SUFFIXES = {".pdf", ".docx", ".md", ".html", ".htm", ".tex"}

# ---------------------------------------------------------------------------
# In-process job store (survives for the lifetime of the server process)
# ---------------------------------------------------------------------------

JobStatus = Literal["queued", "running", "done", "error"]


@dataclass
class IngestJob:
    id: str
    filename: str
    status: JobStatus = "queued"
    paper_id: str | None = None
    chunk_count: int | None = None
    entity_count: int | None = None
    citation_count: int | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status,
            "paper_id": self.paper_id,
            "chunk_count": self.chunk_count,
            "entity_count": self.entity_count,
            "citation_count": self.citation_count,
            "error": self.error,
        }


# Simple thread-safe job registry
_jobs: dict[str, IngestJob] = {}
_lock = threading.Lock()


def _get_job(job_id: str) -> IngestJob | None:
    with _lock:
        return _jobs.get(job_id)


def _all_jobs() -> list[dict]:
    with _lock:
        return [j.to_dict() for j in reversed(list(_jobs.values()))]


def _run_job(job_id: str, tmp_path: Path, db_path: Path) -> None:
    """Execute the ingest pipeline in a background thread."""
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job.status = "running"

    try:
        from pdf_rag.pipeline import ingest_document
        result = ingest_document(tmp_path, db_path=db_path)
        with _lock:
            if job:
                job.status = "done"
                job.paper_id = result.paper_id
                job.chunk_count = result.chunk_count
                job.entity_count = result.entity_count
                job.citation_count = result.citation_count
    except Exception as exc:
        with _lock:
            if job:
                job.status = "error"
                job.error = str(exc)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest")
async def ingest_file(file: UploadFile, request: Request) -> dict:
    """Upload a document and queue it for background ingestion.

    Returns a job_id immediately. Poll GET /api/ingest/jobs/{job_id} for status.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix!r}")

    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    job_id = uuid.uuid4().hex[:12]
    job = IngestJob(id=job_id, filename=file.filename or tmp_path.name)

    with _lock:
        _jobs[job_id] = job

    db_path: Path = request.app.state.db_path
    thread = threading.Thread(target=_run_job, args=(job_id, tmp_path, db_path), daemon=True)
    thread.start()

    return {"job_id": job_id, "filename": job.filename, "status": "queued"}


@router.get("/ingest/jobs")
async def list_jobs() -> list[dict]:
    """Return all ingest jobs (most recent first)."""
    return _all_jobs()


@router.get("/ingest/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    """Return status of a single ingest job."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.delete("/ingest/jobs")
async def clear_jobs() -> dict:
    """Remove all completed/errored jobs from the list."""
    with _lock:
        to_remove = [jid for jid, j in _jobs.items() if j.status in ("done", "error")]
        for jid in to_remove:
            del _jobs[jid]
    return {"removed": len(to_remove)}
