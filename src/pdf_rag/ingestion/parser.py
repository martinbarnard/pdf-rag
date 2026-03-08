"""Docling-based document parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# arXiv IDs: new format 2301.04567, old format hep-th/9901001
_ARXIV_FILENAME_RE = re.compile(r'^(\d{4}\.\d{4,5})(v\d+)?$', re.IGNORECASE)
_ARXIV_TEXT_RE = re.compile(r'arXiv[:\s]+(\d{4}\.\d{4,5})', re.IGNORECASE)

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DocItemLabel

from pdf_rag.config import DOCLING_DEVICE

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".md", ".html", ".htm", ".tex"}


@dataclass
class ParsedDocument:
    title: str
    abstract: str
    authors: list[str]
    year: int | None
    doi: str | None
    sections: list[dict[str, str]]  # [{"heading": str, "text": str}]
    raw_text: str
    file_path: Path
    arxiv_id: str | None = None
    metadata: dict = field(default_factory=dict)


def parse_document(file_path: Path) -> ParsedDocument:
    """Parse a document (PDF, DOCX, MD, HTML, LaTeX) using docling.

    Args:
        file_path: Path to the document.

    Returns:
        ParsedDocument with extracted structure.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported format '{file_path.suffix}'. "
            f"Supported: {sorted(SUPPORTED_SUFFIXES)}"
        )

    pipeline_options = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=DOCLING_DEVICE),
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    result = converter.convert(str(file_path))
    doc = result.document

    title = _extract_title(doc)
    abstract = _extract_abstract(doc)
    sections = _extract_sections(doc)
    raw_text = doc.export_to_text()
    arxiv_id = _extract_arxiv_id(file_path, raw_text)

    return ParsedDocument(
        title=title,
        abstract=abstract,
        authors=[],  # populated by entity extractor
        year=None,
        doi=None,
        arxiv_id=arxiv_id,
        sections=sections,
        raw_text=raw_text,
        file_path=file_path,
    )


def _extract_title(doc) -> str:
    for item, _ in doc.iterate_items():
        if hasattr(item, "label") and item.label == DocItemLabel.TITLE:
            return item.text
    return ""


def _extract_abstract(doc) -> str:
    in_abstract = False
    texts: list[str] = []
    for item, _ in doc.iterate_items():
        if not hasattr(item, "label"):
            continue
        if item.label == DocItemLabel.SECTION_HEADER:
            heading = item.text.strip().lower()
            if "abstract" in heading:
                in_abstract = True
                continue
            elif in_abstract:
                break  # next section — stop
        if in_abstract and item.label in (DocItemLabel.TEXT, DocItemLabel.PARAGRAPH):
            texts.append(item.text)
    return " ".join(texts)


def _extract_arxiv_id(file_path: Path, raw_text: str) -> str | None:
    """Detect the arXiv ID from the filename or document text.

    Priority: filename stem (e.g. 2301.04567v2.pdf) → text regex.
    Returns the bare numeric ID (e.g. "2301.04567") without the version suffix.
    """
    stem = file_path.stem
    m = _ARXIV_FILENAME_RE.match(stem)
    if m:
        return m.group(1)
    m = _ARXIV_TEXT_RE.search(raw_text[:2000])  # header region is enough
    if m:
        return m.group(1)
    return None


def _extract_sections(doc) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_texts: list[str] = []

    for item, _ in doc.iterate_items():
        if not hasattr(item, "label"):
            continue
        if item.label == DocItemLabel.SECTION_HEADER:
            if current_texts:
                sections.append({"heading": current_heading, "text": " ".join(current_texts)})
            current_heading = item.text.strip()
            current_texts = []
        elif item.label in (DocItemLabel.TEXT, DocItemLabel.PARAGRAPH, DocItemLabel.LIST_ITEM):
            current_texts.append(item.text)

    if current_texts:
        sections.append({"heading": current_heading, "text": " ".join(current_texts)})

    return sections
