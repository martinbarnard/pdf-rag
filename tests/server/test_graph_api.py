"""Tests for graph traversal API endpoints."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    from pdf_rag.config import EMBEDDING_DIM
    from pdf_rag.graph.store import GraphStore

    db = tmp_path_factory.mktemp("graph_api") / "api.db"
    store = GraphStore(db)

    store.add_author("a1", "Alice Smith", canonical_name="Alice Smith")
    store.add_author("a2", "Bob Jones", canonical_name="Bob Jones")
    store.add_paper("p1", "Attention Is All You Need", year=2017)
    store.add_paper("p2", "BERT", year=2019)
    store.add_topic("t1", "transformer", canonical_name="Transformer")
    store.add_topic("t2", "self-attention", canonical_name="Self-Attention")

    store.link_author_paper("a1", "p1")
    store.link_author_paper("a2", "p1")
    store.link_author_paper("a1", "p2")
    store.link_paper_topic("p1", "t1")
    store.link_paper_topic("p1", "t2")
    store.link_paper_cites("p2", "p1")
    store.link_related_topics("t1", "t2", weight=0.9)

    vec = [0.001] * EMBEDDING_DIM
    vec[0] = 1.0
    mag = math.sqrt(sum(v * v for v in vec))
    vec = [v / mag for v in vec]
    store.add_chunk("c1", "Chunk about attention.", section="Introduction", embedding=vec)
    store.link_paper_chunk("p1", "c1")

    return db


@pytest.fixture
def app(db_path):
    from pdf_rag.server.main import create_app
    return create_app(db_path=db_path)


@pytest.mark.asyncio
async def test_papers_by_author(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/authors/a1/papers")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    ids = [p["id"] for p in data]
    assert "p1" in ids
    assert "p2" in ids


@pytest.mark.asyncio
async def test_papers_by_author_unknown(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/authors/nobody/papers")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_papers_by_topic(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/topics/t1/papers")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert "p1" in ids


@pytest.mark.asyncio
async def test_related_topics(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/topics/t1/related")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert "t2" in ids


@pytest.mark.asyncio
async def test_coauthors(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/authors/a1/coauthors")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert "a2" in ids


@pytest.mark.asyncio
async def test_citing_papers(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/papers/p1/citing")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert "p2" in ids


@pytest.mark.asyncio
async def test_cited_papers(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/papers/p2/cited")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert "p1" in ids


@pytest.mark.asyncio
async def test_graph_overview(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/graph/overview")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data


@pytest.mark.asyncio
async def test_stats_endpoint(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    for key in ("papers", "authors", "topics", "chunks"):
        assert key in data
    assert data["papers"] >= 1
