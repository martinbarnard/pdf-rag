"""Tests for GLiNER2 entity extractor."""

from __future__ import annotations

import pytest

from pdf_rag.extraction.entities import ENTITY_TYPES, EntityExtractor

TEST_MODEL = "knowledgator/gliner-multitask-large-v0.5"
SCIENTIFIC_TEXT = (
    "Attention Is All You Need was written by Ashish Vaswani at Google Brain. "
    "The transformer architecture uses self-attention mechanisms."
)


class TestEntityExtractorInit:
    def test_default_model_name_set(self) -> None:
        ex = EntityExtractor()
        assert isinstance(ex.model_name, str)

    def test_custom_model_name(self) -> None:
        ex = EntityExtractor(model_name=TEST_MODEL)
        assert ex.model_name == TEST_MODEL

    def test_model_not_loaded_at_init(self) -> None:
        ex = EntityExtractor()
        assert ex._model is None

    def test_entity_types_nonempty(self) -> None:
        assert len(ENTITY_TYPES) > 0
        assert all(isinstance(t, str) for t in ENTITY_TYPES)

    def test_device_param_accepted(self) -> None:
        ex = EntityExtractor(model_name=TEST_MODEL, device="cpu")
        assert ex.device == "cpu"

    def test_default_device_from_config(self) -> None:
        from pdf_rag.config import GLINER_DEVICE
        ex = EntityExtractor()
        assert ex.device == GLINER_DEVICE


class TestEntityExtractorExtract:
    @pytest.fixture(scope="class")
    def extractor(self) -> EntityExtractor:
        return EntityExtractor(model_name=TEST_MODEL)

    def test_returns_list(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT)
        assert isinstance(result, list)

    def test_empty_text_returns_empty(self, extractor: EntityExtractor) -> None:
        result = extractor.extract("")
        assert result == []

    def test_each_entity_has_required_keys(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT)
        for entity in result:
            for key in ("text", "label", "start", "end", "score"):
                assert key in entity, f"Missing key '{key}' in {entity}"

    def test_entity_text_is_string(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT)
        assert all(isinstance(e["text"], str) for e in result)

    def test_entity_score_is_float(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT)
        assert all(isinstance(e["score"], float) for e in result)

    def test_entity_label_is_known_type(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT)
        for entity in result:
            assert entity["label"] in ENTITY_TYPES, f"Unknown label: {entity['label']}"

    def test_detects_person(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT)
        persons = [e["text"] for e in result if e["label"] == "person"]
        assert any("Vaswani" in p for p in persons)

    def test_detects_organization(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT)
        orgs = [e["text"] for e in result if e["label"] == "organization"]
        assert any("Google" in o for o in orgs)

    def test_model_lazy_loaded_after_extract(self, extractor: EntityExtractor) -> None:
        ex = EntityExtractor(model_name=TEST_MODEL)
        assert ex._model is None
        ex.extract("test")
        assert ex._model is not None

    def test_custom_labels(self, extractor: EntityExtractor) -> None:
        result = extractor.extract(SCIENTIFIC_TEXT, labels=["person", "organization"])
        for entity in result:
            assert entity["label"] in ("person", "organization")
