"""Tests for section-aware chunker."""

from __future__ import annotations

import pytest

from pdf_rag.ingestion.chunker import chunk_document


class TestChunkDocument:
    def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            chunk_document({"title": "Test", "sections": []})

    @pytest.mark.skip(reason="chunk_document not yet implemented")
    def test_returns_list_of_dicts(self, sample_text: str) -> None:
        doc = {"title": "T", "sections": [{"text": sample_text, "heading": "Abstract"}]}
        chunks = chunk_document(doc)
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert "id" in chunk
            assert "text" in chunk
            assert "page" in chunk
            assert "section" in chunk

    @pytest.mark.skip(reason="chunk_document not yet implemented")
    def test_respects_chunk_size(self, sample_text: str) -> None:
        doc = {"title": "T", "sections": [{"text": sample_text * 10, "heading": "Body"}]}
        chunks = chunk_document(doc, chunk_size=100, chunk_overlap=10)
        for chunk in chunks:
            assert len(chunk["text"]) <= 120  # allow slight overshoot
