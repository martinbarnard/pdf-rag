"""Tests for docling-based document parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_rag.ingestion.parser import ParsedDocument, parse_document


class TestParsedDocument:
    def test_has_expected_fields(self) -> None:
        doc = ParsedDocument(
            title="Test Paper",
            abstract="An abstract.",
            authors=["Alice", "Bob"],
            year=2024,
            doi="10.1234/test",
            sections=[{"heading": "Introduction", "text": "Some text."}],
            raw_text="Full text.",
            file_path=Path("paper.pdf"),
        )
        assert doc.title == "Test Paper"
        assert doc.authors == ["Alice", "Bob"]
        assert len(doc.sections) == 1

    def test_optional_fields_default(self) -> None:
        doc = ParsedDocument(
            title="",
            abstract="",
            authors=[],
            year=None,
            doi=None,
            sections=[],
            raw_text="",
            file_path=Path("paper.pdf"),
        )
        assert doc.year is None
        assert doc.doi is None


class TestParseDocument:
    def test_unsupported_format_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "paper.xyz"
        bad.write_text("nope")
        with pytest.raises(ValueError, match="Unsupported"):
            parse_document(bad)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_document(tmp_path / "missing.pdf")

    def test_parse_markdown(self, tmp_path: Path) -> None:
        md = tmp_path / "paper.md"
        md.write_text(
            "# My Paper\n\n## Abstract\n\nThis is the abstract.\n\n## Introduction\n\nSome intro text.\n"
        )
        doc = parse_document(md)
        assert isinstance(doc, ParsedDocument)
        assert doc.file_path == md
        assert isinstance(doc.raw_text, str)
        assert len(doc.raw_text) > 0
        assert isinstance(doc.sections, list)

    def test_parse_returns_parsed_document(self, tmp_path: Path) -> None:
        md = tmp_path / "simple.md"
        md.write_text("# Title\n\nSome content here.\n")
        doc = parse_document(md)
        assert isinstance(doc, ParsedDocument)

    def test_sections_have_heading_and_text(self, tmp_path: Path) -> None:
        md = tmp_path / "sections.md"
        md.write_text(
            "# Paper Title\n\n## Introduction\n\nIntro text here.\n\n## Methods\n\nMethods text here.\n"
        )
        doc = parse_document(md)
        for section in doc.sections:
            assert "heading" in section
            assert "text" in section
