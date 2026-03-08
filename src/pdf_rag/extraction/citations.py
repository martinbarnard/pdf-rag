"""Citation extraction from parsed documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pdf_rag.ingestion.parser import ParsedDocument

_DOI_RE = re.compile(r'10\.\d{4,}/\S+')
_ARXIV_RE = re.compile(r'arXiv:(\d{4}\.\d{4,5})', re.IGNORECASE)
_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')

# Section headings considered to contain reference lists
_REFERENCE_HEADINGS = {"references", "bibliography", "works cited", "citations"}


@dataclass
class Citation:
    raw: str
    title: str | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    authors: list[str] = field(default_factory=list)


def extract_citations(document: ParsedDocument) -> list[Citation]:
    """Extract and parse citations from a ParsedDocument.

    Sources (in order of preference):
    1. ``document.metadata["references"]`` — structured list from docling
    2. Reference-section text (sections whose heading matches _REFERENCE_HEADINGS)

    Each raw string is parsed for DOI, arXiv ID, and year.
    Duplicates (by raw text) are removed.

    Args:
        document: A ParsedDocument produced by parser.parse_document.

    Returns:
        List of Citation objects, deduplicated.
    """
    raw_refs: list[str] = []

    # 1. Structured references from docling metadata
    metadata_refs = document.metadata.get("references", [])
    raw_refs.extend(r for r in metadata_refs if isinstance(r, str) and r.strip())

    # 2. Fall back to reference sections if no metadata refs found
    if not raw_refs:
        for section in document.sections:
            heading = section.get("heading", "").strip().lower()
            if heading in _REFERENCE_HEADINGS:
                raw_refs.extend(_split_reference_block(section.get("text", "")))

    # Deduplicate while preserving order
    seen: set[str] = set()
    citations: list[Citation] = []
    for raw in raw_refs:
        raw = raw.strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        citations.append(_parse_citation(raw))

    return citations


def _split_reference_block(text: str) -> list[str]:
    """Split a references section text into individual reference strings."""
    # Split on numbered markers like [1], (1), or blank lines
    numbered = re.split(r'\n(?=\[\d+\]|\(\d+\))', text.strip())
    if len(numbered) > 1:
        return [r.strip() for r in numbered if r.strip()]
    # Fall back: split on double newlines or single newlines starting a new ref
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines


def _parse_citation(raw: str) -> Citation:
    doi_match = _DOI_RE.search(raw)
    arxiv_match = _ARXIV_RE.search(raw)
    year_match = _YEAR_RE.search(raw)

    # Clean DOI: strip trailing punctuation
    doi = re.sub(r'[.,;)\]]+$', '', doi_match.group()) if doi_match else None

    return Citation(
        raw=raw,
        doi=doi,
        arxiv_id=arxiv_match.group(1) if arxiv_match else None,
        year=int(year_match.group()) if year_match else None,
    )
