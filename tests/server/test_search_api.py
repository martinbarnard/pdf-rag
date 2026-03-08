"""Tests for search and RAG query API endpoints."""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    from pdf_rag.config import EMBEDDING_DIM
    from pdf_rag.graph.store import GraphStore

    db = tmp_path_factory.mktemp("search_api") / "search.db"
    store = GraphStore(db)
    store.add_paper("p1", "Attention Is All You Need", year=2017)

    vec = [0.001] * EMBEDDING_DIM
    vec[0] = 1.0
    mag = math.sqrt(sum(v * v for v in vec))
    vec = [v / mag for v in vec]
    store.add_chunk("c1", "The transformer uses self-attention.", section="Abstract", embedding=vec)
    store.link_paper_chunk("p1", "c1")
    return db


@pytest.fixture
def app(db_path):
    from pdf_rag.server.main import create_app
    return create_app(db_path=db_path)


# --- POST /api/search ---

@pytest.mark.asyncio
async def test_search_returns_200(app) -> None:
    with patch("pdf_rag.retriever._call_claude", return_value="Mocked answer."):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/search", json={"query": "transformer attention", "top_k": 3})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_response_shape(app) -> None:
    with patch("pdf_rag.retriever._call_claude", return_value="Answer here."):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/search", json={"query": "transformer"})
    data = r.json()
    assert "chunks" in data
    assert "answer" in data
    assert "sources" in data


@pytest.mark.asyncio
async def test_search_chunks_are_list(app) -> None:
    with patch("pdf_rag.retriever._call_claude", return_value="ok"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/search", json={"query": "attention"})
    assert isinstance(r.json()["chunks"], list)


@pytest.mark.asyncio
async def test_search_missing_query_returns_422(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/search", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_top_k_respected(app) -> None:
    with patch("pdf_rag.retriever._call_claude", return_value="ok"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/search", json={"query": "attention", "top_k": 1})
    assert len(r.json()["chunks"]) <= 1


# --- GET /api/ask (SSE) ---

@pytest.mark.asyncio
async def test_ask_returns_event_stream(app) -> None:
    with patch("pdf_rag.retriever._call_claude", return_value="Streamed answer."):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ask", params={"query": "what is a transformer?"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_ask_response_contains_data(app) -> None:
    with patch("pdf_rag.retriever._call_claude", return_value="The answer is 42."):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ask", params={"query": "transformers"})
    assert "data:" in r.text


@pytest.mark.asyncio
async def test_ask_missing_query_returns_422(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/ask")
    assert r.status_code == 422
