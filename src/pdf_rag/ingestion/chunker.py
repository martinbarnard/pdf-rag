"""Section-aware document chunking."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pdf_rag.config import CHUNK_OVERLAP, CHUNK_SIZE
from pdf_rag.ingestion.parser import ParsedDocument


@dataclass
class Chunk:
    id: str
    text: str
    section: str
    chunk_index: int


def chunk_document(
    document: ParsedDocument,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Split a ParsedDocument into overlapping chunks, preserving section context.

    Each section is chunked independently so section boundaries are never crossed.
    Chunk IDs are deterministic hashes of (file_path, section, chunk_index).

    Args:
        document: ParsedDocument produced by parser.parse_document.
        chunk_size: Maximum character length per chunk.
        chunk_overlap: Character overlap between consecutive chunks.

    Returns:
        List of Chunk objects.
    """
    chunks: list[Chunk] = []

    for section in document.sections:
        heading = section.get("heading", "")
        text = section.get("text", "").strip()
        if not text:
            continue

        section_chunks = _split_text(text, chunk_size, chunk_overlap)
        for idx, chunk_text in enumerate(section_chunks):
            chunk_id = _make_id(str(document.file_path), heading, idx)
            chunks.append(Chunk(id=chunk_id, text=chunk_text, section=heading, chunk_index=idx))

    return chunks


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping chunks on word boundaries."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(words):
        # Greedily consume words until chunk_size is reached
        end = start
        length = 0
        while end < len(words):
            word_len = len(words[end]) + (1 if end > start else 0)
            if length + word_len > chunk_size and end > start:
                break
            length += word_len
            end += 1

        chunk_text = " ".join(words[start:end])
        chunks.append(chunk_text)

        if end >= len(words):
            break

        # Step forward by (chunk_size - chunk_overlap) chars worth of words
        overlap_chars = 0
        step = end
        while step > start and overlap_chars < chunk_overlap:
            overlap_chars += len(words[step - 1]) + 1
            step -= 1

        start = max(start + 1, step)

    return chunks


def _make_id(file_path: str, section: str, index: int) -> str:
    key = f"{file_path}::{section}::{index}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]
