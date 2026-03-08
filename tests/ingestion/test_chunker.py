"""Tests for section-aware document chunker."""

from __future__ import annotations

from pathlib import Path

from pdf_rag.ingestion.chunker import Chunk, chunk_document
from pdf_rag.ingestion.parser import ParsedDocument


def make_doc(**kwargs) -> ParsedDocument:
    defaults = dict(
        title="Test Paper",
        abstract="Short abstract.",
        authors=[],
        year=2024,
        doi=None,
        sections=[],
        raw_text="",
        file_path=Path("paper.pdf"),
    )
    defaults.update(kwargs)
    return ParsedDocument(**defaults)


class TestChunk:
    def test_has_expected_fields(self) -> None:
        c = Chunk(id="abc", text="hello", section="Introduction", chunk_index=0)
        assert c.id == "abc"
        assert c.text == "hello"
        assert c.section == "Introduction"
        assert c.chunk_index == 0


class TestChunkDocument:
    def test_empty_document_returns_empty(self) -> None:
        doc = make_doc(sections=[], raw_text="")
        chunks = chunk_document(doc)
        assert chunks == []

    def test_short_section_produces_one_chunk(self) -> None:
        doc = make_doc(sections=[{"heading": "Abstract", "text": "Short text."}])
        chunks = chunk_document(doc)
        assert len(chunks) == 1
        assert chunks[0].section == "Abstract"
        assert "Short text." in chunks[0].text

    def test_chunk_respects_chunk_size(self) -> None:
        long_text = "word " * 300  # ~1500 chars
        doc = make_doc(sections=[{"heading": "Methods", "text": long_text}])
        chunks = chunk_document(doc, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) <= 150  # tolerance for word boundaries

    def test_overlap_between_chunks(self) -> None:
        long_text = " ".join(f"word{i}" for i in range(200))
        doc = make_doc(sections=[{"heading": "Results", "text": long_text}])
        chunks = chunk_document(doc, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 1
        # end of first chunk should appear somewhere in second chunk
        end_snippet = chunks[0].text.split()[-3:]
        assert any(w in chunks[1].text for w in end_snippet)

    def test_section_heading_preserved(self) -> None:
        doc = make_doc(sections=[
            {"heading": "Introduction", "text": "Intro text here."},
            {"heading": "Methods", "text": "Methods text here."},
        ])
        chunks = chunk_document(doc)
        sections = {c.section for c in chunks}
        assert "Introduction" in sections
        assert "Methods" in sections

    def test_multiple_sections_all_chunked(self) -> None:
        doc = make_doc(sections=[
            {"heading": "Introduction", "text": "Intro text."},
            {"heading": "Methods", "text": "Methods text."},
            {"heading": "Results", "text": "Results text."},
        ])
        chunks = chunk_document(doc)
        assert len(chunks) == 3

    def test_chunk_ids_are_unique(self) -> None:
        long_text = "word " * 300
        doc = make_doc(sections=[{"heading": "Body", "text": long_text}])
        chunks = chunk_document(doc, chunk_size=100, chunk_overlap=10)
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_returns_list_of_chunk_objects(self) -> None:
        doc = make_doc(sections=[{"heading": "Abstract", "text": "Some text."}])
        chunks = chunk_document(doc)
        assert all(isinstance(c, Chunk) for c in chunks)
