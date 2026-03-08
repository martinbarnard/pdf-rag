"""Tests for GLiNER2 entity extractor."""

from __future__ import annotations

import pytest

from pdf_rag.extraction.entities import EntityExtractor


class TestEntityExtractor:
    def test_instantiation(self) -> None:
        extractor = EntityExtractor()
        assert extractor.model_name is not None

    def test_extract_raises_not_implemented(self, sample_text: str) -> None:
        extractor = EntityExtractor()
        with pytest.raises(NotImplementedError):
            extractor.extract(sample_text)

    @pytest.mark.skip(reason="EntityExtractor not yet implemented")
    def test_extract_returns_list_of_dicts(self, sample_text: str) -> None:
        extractor = EntityExtractor()
        entities = extractor.extract(sample_text)
        assert isinstance(entities, list)
        for entity in entities:
            for key in ("text", "label", "start", "end", "score"):
                assert key in entity
