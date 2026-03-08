"""Tests for sentence-transformers embedder."""

from __future__ import annotations

import pytest

from pdf_rag.ingestion.embedder import Embedder


class TestEmbedder:
    def test_instantiation(self) -> None:
        emb = Embedder()
        assert emb.model_name is not None

    def test_encode_raises_not_implemented(self) -> None:
        emb = Embedder()
        with pytest.raises(NotImplementedError):
            emb.encode(["hello world"])

    @pytest.mark.skip(reason="Embedder not yet implemented")
    def test_encode_returns_vectors(self) -> None:
        emb = Embedder()
        result = emb.encode(["hello", "world"])
        assert len(result) == 2
        assert all(isinstance(v, list) for v in result)
        assert all(isinstance(x, float) for x in result[0])
