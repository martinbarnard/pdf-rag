"""Section-aware text chunking."""

from __future__ import annotations

from pdf_rag.config import CHUNK_OVERLAP, CHUNK_SIZE


def chunk_document(
    document: dict,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """Split a parsed document into overlapping chunks.

    Args:
        document: Parsed document dict produced by `parser.parse_document`.
        chunk_size: Maximum number of tokens/characters per chunk.
        chunk_overlap: Number of tokens/characters of overlap between chunks.

    Returns:
        A list of chunk dicts with keys: id, text, page, section.
    """
    raise NotImplementedError
