"""Tests for entity normaliser / deduplicator."""

from __future__ import annotations

import pytest

from pdf_rag.extraction.normaliser import normalise_entities


class TestNormaliseEntities:
    def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            normalise_entities([{"text": "Alice"}])

    @pytest.mark.skip(reason="normalise_entities not yet implemented")
    def test_deduplicates_similar_names(self) -> None:
        entities = [
            {"text": "Alice Smith", "label": "person"},
            {"text": "Alice A. Smith", "label": "person"},
            {"text": "Bob Jones", "label": "person"},
        ]
        result = normalise_entities(entities, threshold=0.85)
        # "Alice Smith" variants should collapse to one entry.
        names = [e["canonical_name"] for e in result]
        assert len([n for n in names if "alice" in n.lower()]) == 1

    @pytest.mark.skip(reason="normalise_entities not yet implemented")
    def test_returns_canonical_name_key(self) -> None:
        entities = [{"text": "Alice Smith", "label": "person"}]
        result = normalise_entities(entities)
        assert "canonical_name" in result[0]
