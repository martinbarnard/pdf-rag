"""Sentence-transformers embedding generation."""

from __future__ import annotations

from pdf_rag.config import DEFAULT_EMBEDDING_MODEL


class Embedder:
    """Wraps a sentence-transformers model for encoding text chunks."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model = None  # lazy-loaded

    def _load(self) -> None:
        raise NotImplementedError

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of float vectors, one per input text.
        """
        raise NotImplementedError
