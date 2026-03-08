"""GLiNER2 entity extraction."""

from __future__ import annotations

from pdf_rag.config import DEFAULT_GLINER_MODEL, GLINER_DEVICE

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
    """Wraps a GLiNER model for named-entity recognition. Lazy-loads the model."""

    def __init__(self, model_name: str = DEFAULT_GLINER_MODEL, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device if device is not None else GLINER_DEVICE
        self._model = None

    def _load(self) -> None:
        from gliner import GLiNER
        self._model = GLiNER.from_pretrained(self.model_name).to(self.device)

    def extract(
        self,
        text: str,
        labels: list[str] | None = None,
    ) -> list[dict]:
        """Extract entities from a text string.

        Args:
            text: The input text to process.
            labels: Entity type labels to detect. Defaults to ENTITY_TYPES.

        Returns:
            List of dicts with keys: text, label, start, end, score.
        """
        if not text:
            return []
        if self._model is None:
            self._load()
        active_labels = labels if labels is not None else ENTITY_TYPES
        entities = self._model.predict_entities(text, active_labels)
        return [
            {
                "text": e["text"],
                "label": e["label"],
                "start": e["start"],
                "end": e["end"],
                "score": float(e["score"]),
            }
            for e in entities
        ]
