"""Tests for kuzu vector similarity search."""

from __future__ import annotations

import math

import pytest

from pdf_rag.config import EMBEDDING_DIM
from pdf_rag.graph.store import GraphStore


def _make_vec(hot_index: int, dim: int = EMBEDDING_DIM) -> list[float]:
    """Return a unit vector with 1.0 at hot_index, small noise elsewhere."""
    vec = [0.001] * dim
    vec[hot_index] = 1.0
    mag = math.sqrt(sum(v * v for v in vec))
    return [v / mag for v in vec]


@pytest.fixture
def store(tmp_path) -> GraphStore:
    return GraphStore(tmp_path / "vec_test.db")


class TestSearchSimilarChunks:
    def test_returns_list(self, store: GraphStore) -> None:
        store.add_chunk("c1", "text", embedding=_make_vec(0))
        result = store.search_similar_chunks(_make_vec(0), top_k=3)
        assert isinstance(result, list)

    def test_empty_store_returns_empty(self, store: GraphStore) -> None:
        result = store.search_similar_chunks(_make_vec(0), top_k=3)
        assert result == []

    def test_returns_top_k_results(self, store: GraphStore) -> None:
        for i in range(5):
            store.add_chunk(f"c{i}", f"chunk {i}", embedding=_make_vec(i))
        result = store.search_similar_chunks(_make_vec(0), top_k=3)
        assert len(result) <= 3

    def test_result_has_required_keys(self, store: GraphStore) -> None:
        store.add_chunk("c1", "hello", section="Intro", embedding=_make_vec(0))
        result = store.search_similar_chunks(_make_vec(0), top_k=1)
        assert len(result) == 1
        row = result[0]
        for key in ("id", "text", "section", "score"):
            assert key in row

    def test_most_similar_ranked_first(self, store: GraphStore) -> None:
        store.add_chunk("similar", "similar chunk", embedding=_make_vec(0))
        store.add_chunk("different", "different chunk", embedding=_make_vec(100))
        result = store.search_similar_chunks(_make_vec(0), top_k=2)
        assert result[0]["id"] == "similar"

    def test_score_is_float(self, store: GraphStore) -> None:
        store.add_chunk("c1", "text", embedding=_make_vec(0))
        result = store.search_similar_chunks(_make_vec(0), top_k=1)
        assert isinstance(result[0]["score"], float)

    def test_chunk_without_embedding_excluded(self, store: GraphStore) -> None:
        store.add_chunk("no_emb", "no embedding chunk")
        store.add_chunk("with_emb", "has embedding", embedding=_make_vec(0))
        result = store.search_similar_chunks(_make_vec(0), top_k=5)
        ids = [r["id"] for r in result]
        assert "with_emb" in ids
        assert "no_emb" not in ids

    def test_scores_ordered_descending(self, store: GraphStore) -> None:
        for i in range(4):
            store.add_chunk(f"c{i}", f"chunk {i}", embedding=_make_vec(i))
        result = store.search_similar_chunks(_make_vec(0), top_k=4)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)
