"""Ingestion trigger API endpoints with background job queue."""

from __future__ import annotations

import shutil
import threading
import uuid
from dataclasses import dataclass
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
    dest_path: str
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
            "dest_path": self.dest_path,
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


def _unique_dest(ingest_dir: Path, filename: str) -> Path:
    """Return a non-colliding path inside ingest_dir for the given filename."""
    dest = ingest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = ingest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _run_job(job_id: str, dest_path: Path, db_path: Path) -> None:
    """Execute the ingest pipeline in a background thread."""
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job.status = "running"

    try:
        from pdf_rag.pipeline import ingest_document
        result = ingest_document(dest_path, db_path=db_path)
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
    # Note: dest_path is NOT deleted — it is the permanent copy in ingest_dir.


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest")
async def ingest_file(file: UploadFile, request: Request) -> dict:
    """Upload a document, save it to the ingest folder, and queue for ingestion.

    The file is copied to app.state.ingest_dir and stays there permanently.
    Returns a job_id immediately. Poll GET /api/ingest/jobs/{job_id} for status.
    """
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix!r}")

    ingest_dir: Path = request.app.state.ingest_dir
    db_path: Path = request.app.state.db_path

    content = await file.read()

    dest_path = _unique_dest(ingest_dir, filename)
    dest_path.write_bytes(content)

    job_id = uuid.uuid4().hex[:12]
    job = IngestJob(id=job_id, filename=filename, dest_path=str(dest_path))

    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_run_job, args=(job_id, dest_path, db_path), daemon=True)
    thread.start()

    return {"job_id": job_id, "filename": filename, "dest_path": str(dest_path), "status": "queued"}


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
    """Remove all completed/errored jobs from the in-memory list."""
    with _lock:
        to_remove = [jid for jid, j in _jobs.items() if j.status in ("done", "error")]
        for jid in to_remove:
            del _jobs[jid]
    return {"removed": len(to_remove)}
