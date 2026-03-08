"""Ingestion trigger API endpoints with background job queue.

Architecture
------------
Uploading a file returns a job_id immediately. The work happens in two stages:

  Stage 1 — prepare (worker thread, parallel):
    parse → chunk → embed → entity extract
    CPU/GPU heavy, no DB access, safe to run concurrently.

  Stage 2 — store (DB-writer thread, serial):
    Drains a queue of PreparedDocument results one at a time.
    kuzu connections are NOT thread-safe; serialising here prevents corruption.

Each IngestJob status progression:
  queued → preparing → storing → done | error
"""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, UploadFile

router = APIRouter(tags=["ingest"])

_ALLOWED_SUFFIXES = {".pdf", ".docx", ".md", ".html", ".htm", ".tex"}

# ---------------------------------------------------------------------------
# Job model
# ---------------------------------------------------------------------------

JobStatus = Literal["queued", "preparing", "storing", "done", "error"]


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


# ---------------------------------------------------------------------------
# IngestManager — concurrent prepare workers + serial DB-writer
# ---------------------------------------------------------------------------

class IngestManager:
    """Manages concurrent prepare workers and a single serial DB-writer thread.

    One instance is created per db_path (stored in module-level registry).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._jobs: dict[str, IngestJob] = {}
        self._lock = threading.Lock()
        self._store_queue: queue.Queue = queue.Queue()
        self._writer = threading.Thread(target=self._db_writer_loop, daemon=True)
        self._writer.start()

    def submit(self, job_id: str, dest_path: Path) -> None:
        """Start a prepare worker for the given (already registered) job."""
        threading.Thread(
            target=self._prepare_worker,
            args=(job_id, dest_path),
            daemon=True,
        ).start()

    def register(self, job: IngestJob) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def all_jobs(self) -> list[dict]:
        with self._lock:
            return [j.to_dict() for j in reversed(list(self._jobs.values()))]

    def get_job(self, job_id: str) -> IngestJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def clear_finished(self) -> int:
        with self._lock:
            to_remove = [jid for jid, j in self._jobs.items() if j.status in ("done", "error")]
            for jid in to_remove:
                del self._jobs[jid]
        return len(to_remove)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_status(self, job_id: str, status: JobStatus, **kwargs) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                for k, v in kwargs.items():
                    setattr(job, k, v)

    def _prepare_worker(self, job_id: str, dest_path: Path) -> None:
        """Stage 1: CPU/GPU heavy work. Runs in a disposable thread (parallel-safe)."""
        self._set_status(job_id, "preparing")
        try:
            from pdf_rag.pipeline import prepare_document
            prepared = prepare_document(dest_path)
            self._set_status(job_id, "storing")
            self._store_queue.put((job_id, prepared))
        except Exception as exc:
            self._set_status(job_id, "error", error=str(exc))

    def _db_writer_loop(self) -> None:
        """Stage 2: Serial DB writes. Single daemon thread, runs forever."""
        from pdf_rag.graph.store import GraphStore
        from pdf_rag.pipeline import store_prepared

        store: GraphStore | None = None

        while True:
            job_id, prepared = self._store_queue.get()
            try:
                if store is None:
                    store = GraphStore(self._db_path)
                result = store_prepared(prepared, store)
                self._set_status(
                    job_id, "done",
                    paper_id=result.paper_id,
                    chunk_count=result.chunk_count,
                    entity_count=result.entity_count,
                    citation_count=result.citation_count,
                )
            except Exception as exc:
                self._set_status(job_id, "error", error=str(exc))
                # Drop the store so next job gets a fresh connection
                store = None
            finally:
                self._store_queue.task_done()


# ---------------------------------------------------------------------------
# Module-level manager registry (keyed by resolved db_path string)
# ---------------------------------------------------------------------------

_managers: dict[str, IngestManager] = {}
_managers_lock = threading.Lock()


def _get_manager(db_path: Path) -> IngestManager:
    key = str(db_path.resolve())
    with _managers_lock:
        if key not in _managers:
            _managers[key] = IngestManager(db_path)
        return _managers[key]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest")
async def ingest_file(file: UploadFile, request: Request) -> dict:
    """Upload a document and queue it for ingestion.

    The file is saved to app.state.ingest_dir permanently.
    Returns a job_id immediately. Poll GET /api/ingest/jobs/{job_id} for status.
    Status progression: queued → preparing → storing → done | error
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

    manager = _get_manager(db_path)
    manager.register(job)
    manager.submit(job_id, dest_path)

    return {"job_id": job_id, "filename": filename, "dest_path": str(dest_path), "status": "queued"}


@router.get("/ingest/jobs")
async def list_jobs(request: Request) -> list[dict]:
    """Return all ingest jobs (most recent first)."""
    db_path: Path = request.app.state.db_path
    return _get_manager(db_path).all_jobs()


@router.get("/ingest/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    """Return status of a single ingest job."""
    db_path: Path = request.app.state.db_path
    job = _get_manager(db_path).get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.delete("/ingest/jobs")
async def clear_jobs(request: Request) -> dict:
    """Remove all completed/errored jobs from the in-memory list."""
    db_path: Path = request.app.state.db_path
    removed = _get_manager(db_path).clear_finished()
    return {"removed": removed}
