"""Tests for sentence-transformers embedder."""

from __future__ import annotations

import pytest

from pdf_rag.ingestion.embedder import Embedder

# Use a tiny model so tests run fast without downloading Qwen3
TEST_MODEL = "all-MiniLM-L6-v2"


class TestEmbedderInit:
    def test_default_model_name_set(self) -> None:
        emb = Embedder()
        assert emb.model_name is not None
        assert isinstance(emb.model_name, str)

    def test_custom_model_name(self) -> None:
        emb = Embedder(model_name=TEST_MODEL)
        assert emb.model_name == TEST_MODEL

    def test_model_not_loaded_at_init(self) -> None:
        emb = Embedder(model_name=TEST_MODEL)
        assert emb._model is None

    def test_device_param_accepted(self) -> None:
        emb = Embedder(model_name=TEST_MODEL, device="cpu")
        assert emb.device == "cpu"

    def test_default_device_from_config(self) -> None:
        from pdf_rag.config import EMBEDDING_DEVICE
        emb = Embedder(model_name=TEST_MODEL)
        assert emb.device == EMBEDDING_DEVICE

    def test_model_loads_on_specified_device(self) -> None:
        emb = Embedder(model_name=TEST_MODEL, device="cpu")
        emb.encode(["test"])
        assert str(emb._model.device) == "cpu"


class TestEmbedderEncode:
    @pytest.fixture
    def embedder(self) -> Embedder:
        return Embedder(model_name=TEST_MODEL)

    def test_encode_returns_list(self, embedder: Embedder) -> None:
        result = embedder.encode(["hello world"])
        assert isinstance(result, list)

    def test_encode_length_matches_input(self, embedder: Embedder) -> None:
        texts = ["first sentence", "second sentence", "third sentence"]
        result = embedder.encode(texts)
        assert len(result) == len(texts)

    def test_encode_returns_float_vectors(self, embedder: Embedder) -> None:
        result = embedder.encode(["hello"])
        assert isinstance(result[0], list)
        assert all(isinstance(x, float) for x in result[0])

    def test_encode_vectors_same_dimension(self, embedder: Embedder) -> None:
        result = embedder.encode(["hello", "world"])
        assert len(result[0]) == len(result[1])

    def test_encode_nonempty_vectors(self, embedder: Embedder) -> None:
        result = embedder.encode(["test"])
        assert len(result[0]) > 0

    def test_encode_empty_list_returns_empty(self, embedder: Embedder) -> None:
        result = embedder.encode([])
        assert result == []

    def test_model_lazy_loaded_after_encode(self, embedder: Embedder) -> None:
        assert embedder._model is None
        embedder.encode(["trigger load"])
        assert embedder._model is not None

    def test_encode_different_texts_different_vectors(self, embedder: Embedder) -> None:
        result = embedder.encode(["cats are great", "quantum physics"])
        assert result[0] != result[1]
