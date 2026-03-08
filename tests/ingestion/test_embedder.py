"""Tests for sentence-transformers embedder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
        emb = Embedder(model_name=TEST_MODEL, device="cpu", backend="local_st")
        emb.encode(["test"])
        assert str(emb._model.device) == "cpu"


class TestEmbedderEncode:
    @pytest.fixture
    def embedder(self) -> Embedder:
        return Embedder(model_name=TEST_MODEL, backend="local_st")

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


class TestEmbedderLocalBackend:
    """Tests for the HTTP /v1/embeddings backend (LM Studio / Ollama)."""

    def _mock_response(self, vectors: list[list[float]]) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "data": [{"embedding": v, "index": i} for i, v in enumerate(vectors)]
        }
        return resp

    def test_local_backend_calls_embeddings_endpoint(self) -> None:
        vec = [0.1, 0.2, 0.3]
        with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_MODEL", "qwen3-embedding"):
                with patch("httpx.post", return_value=self._mock_response([vec])) as mock_post:
                    emb = Embedder(backend="local")
                    result = emb.encode(["hello"])
        assert mock_post.called
        assert "http://localhost:1234" in mock_post.call_args[0][0]
        assert "/v1/embeddings" in mock_post.call_args[0][0]

    def test_local_backend_returns_correct_vectors(self) -> None:
        vecs = [[0.1, 0.2], [0.3, 0.4]]
        with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_MODEL", "test"):
                with patch("httpx.post", return_value=self._mock_response(vecs)):
                    emb = Embedder(backend="local")
                    result = emb.encode(["a", "b"])
        assert result == vecs

    def test_local_backend_sends_model_name(self) -> None:
        with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_MODEL", "my-embed-model"):
                with patch("httpx.post", return_value=self._mock_response([[0.0]])) as mock_post:
                    emb = Embedder(backend="local")
                    emb.encode(["test"])
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "my-embed-model"

    def test_local_backend_sends_all_texts(self) -> None:
        texts = ["one", "two", "three"]
        vecs = [[float(i)] for i in range(3)]
        with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_MODEL", "test"):
                with patch("httpx.post", return_value=self._mock_response(vecs)) as mock_post:
                    emb = Embedder(backend="local")
                    emb.encode(texts)
        payload = mock_post.call_args[1]["json"]
        assert payload["input"] == texts

    def test_local_backend_empty_returns_empty(self) -> None:
        emb = Embedder(backend="local")
        assert emb.encode([]) == []

    def test_local_backend_no_model_load(self) -> None:
        """Local backend must not load sentence-transformers."""
        with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_MODEL", "test"):
                with patch("httpx.post", return_value=self._mock_response([[0.1]])):
                    emb = Embedder(backend="local")
                    emb.encode(["hello"])
        assert emb._model is None

    def test_auto_backend_uses_local_when_reachable(self) -> None:
        with patch("pdf_rag.ingestion.embedder.probe_local", return_value=True):
            with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_BASE_URL", "http://localhost:1234"):
                with patch("pdf_rag.ingestion.embedder.LOCAL_EMBEDDING_MODEL", "test"):
                    with patch("httpx.post", return_value=self._mock_response([[0.5]])) as mock_post:
                        emb = Embedder(backend="auto")
                        emb.encode(["hello"])
        assert mock_post.called

    def test_auto_backend_uses_local_st_when_not_reachable(self) -> None:
        with patch("pdf_rag.ingestion.embedder.probe_local", return_value=False):
            emb = Embedder(model_name=TEST_MODEL, backend="auto", device="cpu")
            result = emb.encode(["hello"])
        assert isinstance(result[0], list)
        assert emb._model is not None
