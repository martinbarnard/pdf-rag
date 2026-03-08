"""GLiNER2 entity extraction."""

from __future__ import annotations

from pdf_rag.config import DEFAULT_GLINER_MODEL

# Entity types recognised by the extractor.
ENTITY_TYPES: list[str] = [
    "person",
    "organization",
    "location",
    "topic",
    "method",
    "dataset",
]


class EntityExtractor:
    """Wraps a GLiNER model for named-entity recognition over chunk text."""

    def __init__(self, model_name: str = DEFAULT_GLINER_MODEL) -> None:
        self.model_name = model_name
        self._model = None  # lazy-loaded

    def _load(self) -> None:
        raise NotImplementedError

    def extract(self, text: str) -> list[dict]:
        """Extract entities from a text string.

        Args:
            text: The input text to process.

        Returns:
            A list of entity dicts with keys: text, label, start, end, score.
        """
        raise NotImplementedError
