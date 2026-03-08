"""arXiv search and ingest endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["arxiv"])


class ArxivSearchRequest(BaseModel):
    terms: list[str] = []
    author: str = ""
    top_k: int = 10


class ArxivIngestRequest(BaseModel):
    arxiv_id: str


@router.post("/arxiv/search")
async def arxiv_search(body: ArxivSearchRequest) -> dict:
    """Search arXiv by keyword terms and/or author name.

    Returns a list of ArxivResult dicts plus an attribution string.
    Does not require a paper to exist in the graph.
    """
    from pdf_rag.arxiv import ArxivClient

    terms = [t.strip() for t in body.terms if t.strip()]
    if body.author.strip():
        terms.append(body.author.strip())

    if not terms:
        raise HTTPException(status_code=422, detail="Provide at least one term or author")

    top_k = min(body.top_k, 25)
    client = ArxivClient()
    results = client.search(terms=terms, max_results=top_k)

    return {
        "results": [r.to_dict() for r in results],
        "attribution": (
            "Results from arXiv.org. Thank you to arXiv for use of its open access interoperability."
        ),
    }


@router.post("/arxiv/ingest")
async def arxiv_ingest(body: ArxivIngestRequest, request: Request) -> dict:
    """Download a paper from arXiv by ID and queue it for ingestion.

    Downloads the PDF to ingest_dir, then submits an ingest job.
    Returns a job_id to poll via GET /api/ingest/jobs/{job_id}.
    """
    import urllib.request
    import uuid
    from pathlib import Path

    arxiv_id = body.arxiv_id.strip()
    if not arxiv_id:
        raise HTTPException(status_code=422, detail="arxiv_id is required")

    ingest_dir: Path = request.app.state.ingest_dir
    db_path: Path = request.app.state.db_path

    dest = ingest_dir / f"{arxiv_id}.pdf"
    if not dest.exists():
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        try:
            urllib.request.urlretrieve(pdf_url, dest)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to download {arxiv_id}: {e}")

    from pdf_rag.server.routers.ingest import IngestJob, _get_manager

    job_id = uuid.uuid4().hex[:12]
    job = IngestJob(id=job_id, filename=dest.name, dest_path=str(dest))
    manager = _get_manager(db_path)
    manager.register(job)
    manager.submit(job_id, dest)

    return {"job_id": job_id, "arxiv_id": arxiv_id, "filename": dest.name, "status": "queued"}
