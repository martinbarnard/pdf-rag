"""Sentence-transformers embedding generation."""

from __future__ import annotations

from pdf_rag.config import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DEVICE


class Embedder:
    """Wraps a sentence-transformers model for encoding text. Lazy-loads the model."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device if device is not None else EMBEDDING_DEVICE
        self._model = None

    def _load(self) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name, device=self.device)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of float vectors, one per input text.
        """
        if not texts:
            return []
        if self._model is None:
            self._load()
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]
