"""Ingestion pipeline orchestrator.

Coordinates: parse → chunk → embed → extract entities → store in graph.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pdf_rag.config import DEFAULT_DB_PATH
from pdf_rag.extraction.citations import extract_citations
from pdf_rag.extraction.entities import EntityExtractor
from pdf_rag.extraction.normaliser import normalise_authors, normalise_topics
from pdf_rag.graph.store import GraphStore
from pdf_rag.ingestion.chunker import chunk_document
from pdf_rag.ingestion.embedder import Embedder
from pdf_rag.ingestion.parser import parse_document
from pdf_rag.llm import generate_title


@dataclass
class IngestResult:
    file_path: Path
    paper_id: str
    chunk_count: int
    entity_count: int
    citation_count: int


def ingest_document(
    file_path: Path,
    db_path: Path | None = None,
    embedder: Embedder | None = None,
    extractor: EntityExtractor | None = None,
) -> IngestResult:
    """Run the full ingestion pipeline for a single document.

    Steps:
      1. Parse document with docling
      2. Chunk into sections
      3. Embed chunks
      4. Extract entities (authors, topics) with GLiNER2
      5. Extract citations
      6. Normalise authors and topics
      7. Store everything in kuzu graph

    Args:
        file_path: Path to the document to ingest.
        db_path: Path to the kuzu database. Defaults to DEFAULT_DB_PATH.
        embedder: Optional pre-loaded Embedder (for reuse across calls).
        extractor: Optional pre-loaded EntityExtractor (for reuse across calls).

    Returns:
        IngestResult with counts of what was stored.

    Raises:
        FileNotFoundError: If file_path does not exist.
        ValueError: If the file format is not supported.
    """
    db_path = db_path or DEFAULT_DB_PATH
    embedder = embedder or Embedder()
    extractor = extractor or EntityExtractor()

    # 1. Parse
    doc = parse_document(file_path)

    # 2. Chunk
    chunks = chunk_document(doc)

    # 3. Embed
    texts = [c.text for c in chunks]
    embeddings = embedder.encode(texts) if texts else []

    # 4. Entity extraction — run over abstract + section texts
    sample_text = " ".join([doc.abstract] + [s["text"] for s in doc.sections[:3]])
    raw_entities = extractor.extract(sample_text) if sample_text.strip() else []

    raw_authors = [e["text"] for e in raw_entities if e["label"] == "person"]
    raw_topics = [e["text"] for e in raw_entities if e["label"] in ("topic", "method")]

    # 5. Citations
    citations = extract_citations(doc)

    # 6. Normalise
    authors = normalise_authors(raw_authors)
    topics = normalise_topics(raw_topics)

    # 7. Store
    store = GraphStore(db_path)
    paper_id = _paper_id(file_path)

    title = doc.title or generate_title(
        doc.abstract or " ".join(s["text"] for s in doc.sections[:2]),
        fallback=file_path.stem,
    )
    store.add_paper(
        id=paper_id,
        title=title,
        abstract=doc.abstract,
        year=doc.year or 0,
        doi=doc.doi or "",
        file_path=str(file_path),
    )

    # Store authors and link to paper
    for author in authors:
        author_id = _slug(author["canonical_name"])
        store.add_author(
            id=author_id,
            name=author["canonical_name"],
            canonical_name=author["canonical_name"],
        )
        store.link_author_paper(author_id, paper_id)

    # Store topics and link to paper
    for topic in topics:
        topic_id = _slug(topic["canonical_name"])
        store.add_topic(
            id=topic_id,
            name=topic["canonical_name"],
            canonical_name=topic["canonical_name"],
        )
        store.link_paper_topic(paper_id, topic_id)

    # Store chunks with embeddings
    for chunk, embedding in zip(chunks, embeddings):
        store.add_chunk(
            id=chunk.id,
            text=chunk.text,
            section=chunk.section,
            embedding=embedding,
        )
        store.link_paper_chunk(paper_id, chunk.id)

    entity_count = len(authors) + len(topics)
    return IngestResult(
        file_path=file_path,
        paper_id=paper_id,
        chunk_count=len(chunks),
        entity_count=entity_count,
        citation_count=len(citations),
    )


def _paper_id(file_path: Path) -> str:
    """Deterministic paper ID from file path."""
    return hashlib.sha1(str(file_path.resolve()).encode()).hexdigest()[:16]


def _slug(name: str) -> str:
    """Deterministic node ID from a name string."""
    return hashlib.sha1(name.lower().strip().encode()).hexdigest()[:12]
