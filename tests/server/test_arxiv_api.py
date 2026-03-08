"""Tests for the arXiv search and ingest API endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


SAMPLE_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.04567v2</id>
    <title>Attention Is All You Need</title>
    <summary>We propose a new architecture.</summary>
    <published>2017-06-12T00:00:00Z</published>
    <author><name>Ashish Vaswani</name></author>
    <category term="cs.CL"/>
    <link title="pdf" href="https://arxiv.org/pdf/2301.04567v2"/>
  </entry>
</feed>
"""


def _mock_httpx(text: str = SAMPLE_ATOM):
    resp = MagicMock()
    resp.status_code = 200
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    from pdf_rag.graph.store import GraphStore
    db = tmp_path_factory.mktemp("arxiv_api") / "api.db"
    GraphStore(db)  # initialise schema
    return db


@pytest.fixture(scope="module")
def ingest_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("arxiv_ingest")


@pytest.fixture(scope="module")
def app(db_path, ingest_dir):
    from pdf_rag.server.main import create_app
    return create_app(db_path=db_path, ingest_dir=ingest_dir)


@pytest.fixture
def client(app):
    import anyio
    import httpx
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# POST /api/arxiv/search
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_search_returns_results(client):
    with patch("httpx.get", return_value=_mock_httpx()):
        resp = await client.post("/api/arxiv/search", json={"terms": ["transformer"], "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "attribution" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["arxiv_id"] == "2301.04567"


@pytest.mark.anyio
async def test_search_by_author(client):
    with patch("httpx.get", return_value=_mock_httpx()):
        resp = await client.post("/api/arxiv/search", json={"author": "Vaswani", "top_k": 5})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


@pytest.mark.anyio
async def test_search_requires_terms_or_author(client):
    resp = await client.post("/api/arxiv/search", json={"top_k": 5})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_caps_top_k(client):
    """top_k is capped at 25 server-side."""
    with patch("httpx.get", return_value=_mock_httpx()):
        resp = await client.post("/api/arxiv/search", json={"terms": ["test"], "top_k": 100})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/arxiv/ingest
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_returns_job_id(client, ingest_dir):
    fake_pdf = ingest_dir / "2301.04567.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")  # pre-create so no download needed

    resp = await client.post("/api/arxiv/ingest", json={"arxiv_id": "2301.04567"})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["arxiv_id"] == "2301.04567"
    assert data["status"] == "queued"


@pytest.mark.anyio
async def test_ingest_missing_arxiv_id(client):
    resp = await client.post("/api/arxiv/ingest", json={"arxiv_id": ""})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ingest_job_is_pollable(client, ingest_dir):
    fake_pdf = ingest_dir / "9999.99999.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    resp = await client.post("/api/arxiv/ingest", json={"arxiv_id": "9999.99999"})
    job_id = resp.json()["job_id"]

    poll = await client.get(f"/api/ingest/jobs/{job_id}")
    assert poll.status_code == 200
    assert poll.json()["status"] in {"queued", "preparing", "storing", "done", "error"}
