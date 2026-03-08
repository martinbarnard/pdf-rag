"""Tests for citation extraction."""

from __future__ import annotations

from pathlib import Path

from pdf_rag.extraction.citations import Citation, extract_citations
from pdf_rag.ingestion.parser import ParsedDocument


def make_doc(sections=None, references=None) -> ParsedDocument:
    return ParsedDocument(
        title="Test Paper",
        abstract="",
        authors=[],
        year=None,
        doi=None,
        sections=sections or [],
        raw_text="",
        file_path=Path("paper.pdf"),
        metadata={"references": references or []},
    )


class TestCitation:
    def test_has_expected_fields(self) -> None:
        c = Citation(raw="Vaswani et al. 2017.", title="Attention is all you need", year=2017)
        assert c.raw == "Vaswani et al. 2017."
        assert c.year == 2017
        assert c.doi is None
        assert c.arxiv_id is None

    def test_optional_fields_default_none(self) -> None:
        c = Citation(raw="Some ref.")
        assert c.title is None
        assert c.year is None
        assert c.doi is None
        assert c.arxiv_id is None


class TestExtractCitations:
    def test_empty_document_returns_empty(self) -> None:
        doc = make_doc()
        assert extract_citations(doc) == []

    def test_extracts_from_metadata_references(self) -> None:
        doc = make_doc(references=[
            "Vaswani, A. et al. (2017). Attention is all you need. NeurIPS.",
            "Brown, T. et al. Language Models are Few-Shot Learners. arXiv:2005.14165, 2020.",
        ])
        result = extract_citations(doc)
        assert len(result) == 2

    def test_returns_citation_objects(self) -> None:
        doc = make_doc(references=["Some reference text."])
        result = extract_citations(doc)
        assert all(isinstance(c, Citation) for c in result)

    def test_extracts_doi(self) -> None:
        doc = make_doc(references=[
            "He et al. (2016). Deep residual learning. https://doi.org/10.1109/CVPR.2016.90"
        ])
        result = extract_citations(doc)
        assert result[0].doi == "10.1109/CVPR.2016.90"

    def test_extracts_arxiv_id(self) -> None:
        doc = make_doc(references=[
            "Brown et al. Language Models are Few-Shot Learners. arXiv:2005.14165"
        ])
        result = extract_citations(doc)
        assert result[0].arxiv_id == "2005.14165"

    def test_extracts_year(self) -> None:
        doc = make_doc(references=[
            "LeCun, Y. et al. (1998). Gradient-based learning applied to document recognition."
        ])
        result = extract_citations(doc)
        assert result[0].year == 1998

    def test_raw_text_preserved(self) -> None:
        raw = "Vaswani et al. (2017). Attention is all you need."
        doc = make_doc(references=[raw])
        result = extract_citations(doc)
        assert result[0].raw == raw

    def test_extracts_from_references_section(self) -> None:
        doc = make_doc(sections=[
            {"heading": "References", "text": (
                "[1] Vaswani et al. (2017). Attention is all you need.\n"
                "[2] Devlin et al. (2019). BERT. arXiv:1810.04805"
            )}
        ])
        result = extract_citations(doc)
        assert len(result) >= 1

    def test_no_duplicate_citations(self) -> None:
        same = "Vaswani et al. (2017). Attention is all you need."
        doc = make_doc(references=[same, same])
        result = extract_citations(doc)
        raws = [c.raw for c in result]
        assert len(raws) == len(set(raws))
