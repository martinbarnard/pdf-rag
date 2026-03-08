"""Tests for search and RAG query API endpoints."""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


def _unit_vec(dim: int) -> list[float]:
    import math
    vec = [0.001] * dim
    vec[0] = 1.0
    mag = math.sqrt(sum(v * v for v in vec))
    return [v / mag for v in vec]


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    from pdf_rag.config import EMBEDDING_DIM
    from pdf_rag.graph.store import GraphStore

    db = tmp_path_factory.mktemp("search_api") / "search.db"
    store = GraphStore(db)
    store.add_paper("p1", "Attention Is All You Need", year=2017)
    store.add_chunk("c1", "The transformer uses self-attention.", section="Abstract", embedding=_unit_vec(EMBEDDING_DIM))
    store.link_paper_chunk("p1", "c1")
    return db


@pytest.fixture
def mock_embedder():
    from unittest.mock import MagicMock
    from pdf_rag.config import EMBEDDING_DIM
    emb = MagicMock()
    emb.encode.side_effect = lambda texts: [_unit_vec(EMBEDDING_DIM) for _ in texts]
    return emb


@pytest.fixture
def app(db_path):
    from pdf_rag.server.main import create_app
    return create_app(db_path=db_path)


# --- POST /api/search ---

@pytest.mark.asyncio
async def test_search_returns_200(app, mock_embedder) -> None:
    with patch("pdf_rag.retriever.call_llm", return_value="Mocked answer."):
        with patch("pdf_rag.retriever.Embedder", return_value=mock_embedder):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/search", json={"query": "transformer attention", "top_k": 3})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_response_shape(app, mock_embedder) -> None:
    with patch("pdf_rag.retriever.call_llm", return_value="Answer here."):
        with patch("pdf_rag.retriever.Embedder", return_value=mock_embedder):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/search", json={"query": "transformer"})
    data = r.json()
    assert "chunks" in data
    assert "answer" in data
    assert "sources" in data


@pytest.mark.asyncio
async def test_search_chunks_are_list(app, mock_embedder) -> None:
    with patch("pdf_rag.retriever.call_llm", return_value="ok"):
        with patch("pdf_rag.retriever.Embedder", return_value=mock_embedder):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/search", json={"query": "attention"})
    assert isinstance(r.json()["chunks"], list)


@pytest.mark.asyncio
async def test_search_missing_query_returns_422(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/search", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_top_k_respected(app, mock_embedder) -> None:
    with patch("pdf_rag.retriever.call_llm", return_value="ok"):
        with patch("pdf_rag.retriever.Embedder", return_value=mock_embedder):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/search", json={"query": "attention", "top_k": 1})
    assert len(r.json()["chunks"]) <= 1


# --- GET /api/ask (SSE) ---

@pytest.mark.asyncio
async def test_ask_returns_event_stream(app, mock_embedder) -> None:
    with patch("pdf_rag.retriever.call_llm", return_value="Streamed answer."):
        with patch("pdf_rag.retriever.Embedder", return_value=mock_embedder):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/ask", params={"query": "what is a transformer?"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_ask_response_contains_data(app, mock_embedder) -> None:
    with patch("pdf_rag.retriever.call_llm", return_value="The answer is 42."):
        with patch("pdf_rag.retriever.Embedder", return_value=mock_embedder):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/ask", params={"query": "transformers"})
    assert "data:" in r.text


@pytest.mark.asyncio
async def test_ask_missing_query_returns_422(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/ask")
    assert r.status_code == 422
