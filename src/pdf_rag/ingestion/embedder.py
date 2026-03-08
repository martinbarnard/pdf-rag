"""Embedding generation with automatic backend selection.

Backends:
  "auto"     — use LM Studio /v1/embeddings if reachable, else sentence-transformers
  "local"    — always call LM Studio / Ollama /v1/embeddings endpoint
  "local_st" — always use sentence-transformers in-process

When using the local backend, the embedding model must already be loaded in
LM Studio (or whichever OpenAI-compatible server is running).
"""

from __future__ import annotations

import os

from pdf_rag.config import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_BACKEND as _CFG_BACKEND,
    EMBEDDING_DEVICE,
    LOCAL_EMBEDDING_BASE_URL as _CFG_EMB_BASE_URL,
    LOCAL_EMBEDDING_MODEL as _CFG_EMB_MODEL,
)

# Allow env-var overrides
LOCAL_EMBEDDING_BASE_URL: str = os.environ.get("LOCAL_EMBEDDING_BASE_URL", _CFG_EMB_BASE_URL)
LOCAL_EMBEDDING_MODEL: str = os.environ.get("LOCAL_EMBEDDING_MODEL", _CFG_EMB_MODEL)


def probe_local() -> bool:
    """Return True if the local embedding server is reachable.

    Reuses the LLM probe since both share the same LM Studio instance.
    """
    from pdf_rag.llm import probe_local as _probe
    return _probe()


class Embedder:
    """Encodes text to float vectors.

    Backend selection (via `backend` arg or EMBEDDING_BACKEND config):
      - "auto"     : probe local server; use it if up, else sentence-transformers
      - "local"    : always use /v1/embeddings HTTP endpoint
      - "local_st" : always use sentence-transformers in-process
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        device: str | None = None,
        backend: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device if device is not None else EMBEDDING_DEVICE
        self.backend = backend if backend is not None else os.environ.get("EMBEDDING_BACKEND", _CFG_BACKEND)
        self._model = None  # sentence-transformers model, None when using local HTTP

    def _load(self) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name, device=self.device)

    def _resolved_backend(self) -> str:
        """Resolve 'auto' to 'local' or 'local_st' at call time."""
        if self.backend == "auto":
            return "local" if probe_local() else "local_st"
        return self.backend

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of float vectors, one per input text.
        """
        if not texts:
            return []
        resolved = self._resolved_backend()
        if resolved == "local":
            return self._encode_local(texts)
        # local_st or any unknown value
        if self._model is None:
            self._load()
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    def _encode_local(self, texts: list[str]) -> list[list[float]]:
        """Call the local /v1/embeddings endpoint."""
        import httpx

        url = LOCAL_EMBEDDING_BASE_URL.rstrip("/") + "/v1/embeddings"
        resp = httpx.post(
            url,
            json={"model": LOCAL_EMBEDDING_MODEL, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # OpenAI spec: data is a list sorted by index
        data.sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data]
