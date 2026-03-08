"""Tests for the RAG retrieval pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdf_rag.retriever import RetrievalResult, retrieve


@pytest.fixture(scope="module")
def populated_store(tmp_path_factory):
    """GraphStore with a few chunks pre-loaded for retrieval tests."""
    from pdf_rag.config import EMBEDDING_DIM
    from pdf_rag.graph.store import GraphStore
    import math

    db_path = tmp_path_factory.mktemp("retriever") / "ret.db"
    store = GraphStore(db_path)

    store.add_paper("p1", "Transformers", abstract="Self-attention paper", year=2017)
    store.add_author("a1", "Vaswani", canonical_name="Ashish Vaswani")
    store.add_topic("t1", "transformer", canonical_name="Transformer")
    store.link_author_paper("a1", "p1")
    store.link_paper_topic("p1", "t1")

    # Add chunks with embeddings pointing in distinct directions
    for i in range(3):
        vec = [0.001] * EMBEDDING_DIM
        vec[i] = 1.0
        mag = math.sqrt(sum(v * v for v in vec))
        vec = [v / mag for v in vec]
        store.add_chunk(f"c{i}", f"Chunk text {i} about transformers.", section="Introduction", embedding=vec)
        store.link_paper_chunk("p1", f"c{i}")

    return store, db_path


class TestRetrievalResult:
    def test_has_expected_fields(self) -> None:
        r = RetrievalResult(
            chunks=[{"id": "c1", "text": "text", "section": "Intro", "score": 0.9}],
            context="some context",
            answer="an answer",
            sources=["paper1"],
        )
        assert r.answer == "an answer"
        assert len(r.chunks) == 1


class TestRetrieve:
    def test_returns_retrieval_result(self, populated_store) -> None:
        store, db_path = populated_store
        with patch("pdf_rag.retriever.call_llm", return_value="Mocked answer."):
            result = retrieve("what is a transformer?", db_path=db_path)
        assert isinstance(result, RetrievalResult)

    def test_chunks_returned(self, populated_store) -> None:
        store, db_path = populated_store
        with patch("pdf_rag.retriever.call_llm", return_value="Mocked answer."):
            result = retrieve("transformer attention", db_path=db_path, top_k=2)
        assert len(result.chunks) <= 2
        assert all("text" in c for c in result.chunks)

    def test_answer_is_string(self, populated_store) -> None:
        store, db_path = populated_store
        with patch("pdf_rag.retriever.call_llm", return_value="Test answer."):
            result = retrieve("transformers", db_path=db_path)
        assert isinstance(result.answer, str)

    def test_context_includes_chunk_text(self, populated_store) -> None:
        store, db_path = populated_store
        with patch("pdf_rag.retriever.call_llm", return_value="ok"):
            result = retrieve("transformers", db_path=db_path, top_k=1)
        assert any(c["text"] in result.context for c in result.chunks)

    def test_empty_db_returns_no_chunks(self, tmp_path) -> None:
        from pdf_rag.graph.store import GraphStore
        GraphStore(tmp_path / "empty.db")
        with patch("pdf_rag.retriever.call_llm", return_value="No results."):
            result = retrieve("anything", db_path=tmp_path / "empty.db")
        assert result.chunks == []

    def test_top_k_respected(self, populated_store) -> None:
        store, db_path = populated_store
        with patch("pdf_rag.retriever.call_llm", return_value="ok"):
            result = retrieve("transformers", db_path=db_path, top_k=1)
        assert len(result.chunks) <= 1
