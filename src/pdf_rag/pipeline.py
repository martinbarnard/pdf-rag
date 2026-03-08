"""Ingestion pipeline orchestrator.

Coordinates: parse → chunk → embed → extract entities → store in graph.

The pipeline is split into two phases to allow safe concurrent ingestion:

  prepare_document()  — CPU-heavy: parse, chunk, embed, extract.
                        Safe to run in parallel threads.
                        Returns a PreparedDocument (no DB access).

  store_prepared()    — DB write: store PreparedDocument in kuzu.
                        Must be called from a SINGLE thread at a time.

ingest_document()     — Convenience wrapper that runs both phases in sequence
                        (used by the CLI and tests).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from pdf_rag.config import DEFAULT_DB_PATH
from pdf_rag.extraction.citations import extract_citations
from pdf_rag.extraction.entities import EntityExtractor
from pdf_rag.extraction.normaliser import normalise_authors, normalise_topics
from pdf_rag.graph.store import GraphStore
from pdf_rag.ingestion.chunker import chunk_document
from pdf_rag.ingestion.embedder import Embedder
from pdf_rag.ingestion.parser import parse_document


@dataclass
class IngestResult:
    file_path: Path
    paper_id: str
    chunk_count: int
    entity_count: int
    citation_count: int


@dataclass
class _PreparedChunk:
    id: str
    text: str
    section: str
    embedding: list[float]


@dataclass
class PreparedDocument:
    """All data needed to write one document to the graph — no DB handle held."""
    file_path: Path
    paper_id: str
    title: str
    abstract: str
    year: int
    doi: str
    arxiv_id: str
    authors: list[dict]           # [{"canonical_name": str}]
    topics: list[dict]            # [{"canonical_name": str}]
    chunks: list[_PreparedChunk]
    citation_count: int


def prepare_document(
    file_path: Path,
    embedder: Embedder | None = None,
    extractor: EntityExtractor | None = None,
) -> PreparedDocument:
    """Parse, embed, and extract entities — no DB access.

    Safe to call from multiple threads concurrently.

    Args:
        file_path: Path to the document to ingest.
        embedder: Optional pre-loaded Embedder (for reuse across calls).
        extractor: Optional pre-loaded EntityExtractor (for reuse across calls).

    Returns:
        PreparedDocument ready to be passed to store_prepared().
    """
    embedder = embedder or Embedder()
    extractor = extractor or EntityExtractor()

    doc = parse_document(file_path)
    chunks = chunk_document(doc)

    texts = [c.text for c in chunks]
    embeddings = embedder.encode(texts) if texts else []

    sample_text = " ".join([doc.abstract] + [s["text"] for s in doc.sections[:3]])
    raw_entities = extractor.extract(sample_text) if sample_text.strip() else []

    raw_authors = [e["text"] for e in raw_entities if e["label"] == "person"]
    raw_topics = [e["text"] for e in raw_entities if e["label"] in ("topic", "method")]

    citations = extract_citations(doc)
    authors = normalise_authors(raw_authors)
    topics = normalise_topics(raw_topics)

    paper_id = _paper_id(file_path)
    # Title priority: docling TITLE label → first section heading → filename stem
    # (The local Qwen3 LLM is a reasoning model and produces unusable output for
    # short completions, so LLM title generation is disabled.)
    title = (
        doc.title
        or (doc.sections[0]["heading"] if doc.sections and doc.sections[0]["heading"] else "")
        or file_path.stem
    )

    prepared_chunks = [
        _PreparedChunk(id=c.id, text=c.text, section=c.section, embedding=list(emb))
        for c, emb in zip(chunks, embeddings)
    ]

    return PreparedDocument(
        file_path=file_path,
        paper_id=paper_id,
        title=title,
        abstract=doc.abstract,
        year=doc.year or 0,
        doi=doc.doi or "",
        arxiv_id=doc.arxiv_id or "",
        authors=authors,
        topics=topics,
        chunks=prepared_chunks,
        citation_count=len(citations),
    )


def store_prepared(prepared: PreparedDocument, store: GraphStore) -> IngestResult:
    """Write a PreparedDocument into the graph.

    Must be called from a single thread (kuzu connections are not thread-safe).

    Args:
        prepared: Output of prepare_document().
        store: An open GraphStore instance (caller owns lifetime).

    Returns:
        IngestResult with counts of what was stored.
    """
    store.add_paper(
        id=prepared.paper_id,
        title=prepared.title,
        abstract=prepared.abstract,
        year=prepared.year,
        doi=prepared.doi,
        arxiv_id=prepared.arxiv_id,
        file_path=str(prepared.file_path),
    )

    for author in prepared.authors:
        author_id = _slug(author["canonical_name"])
        store.add_author(
            id=author_id,
            name=author["canonical_name"],
            canonical_name=author["canonical_name"],
        )
        store.link_author_paper(author_id, prepared.paper_id)

    for topic in prepared.topics:
        topic_id = _slug(topic["canonical_name"])
        store.add_topic(
            id=topic_id,
            name=topic["canonical_name"],
            canonical_name=topic["canonical_name"],
        )
        store.link_paper_topic(prepared.paper_id, topic_id)

    for chunk in prepared.chunks:
        store.add_chunk(
            id=chunk.id,
            text=chunk.text,
            section=chunk.section,
            embedding=chunk.embedding,
        )
        store.link_paper_chunk(prepared.paper_id, chunk.id)

    return IngestResult(
        file_path=prepared.file_path,
        paper_id=prepared.paper_id,
        chunk_count=len(prepared.chunks),
        entity_count=len(prepared.authors) + len(prepared.topics),
        citation_count=prepared.citation_count,
    )


def ingest_document(
    file_path: Path,
    db_path: Path | None = None,
    embedder: Embedder | None = None,
    extractor: EntityExtractor | None = None,
) -> IngestResult:
    """Run the full ingestion pipeline for a single document (prepare + store).

    Convenience wrapper for CLI / test use. For concurrent server use,
    call prepare_document() in worker threads and store_prepared() serially
    via IngestManager in pdf_rag.server.routers.ingest.

    Args:
        file_path: Path to the document to ingest.
        db_path: Path to the kuzu database. Defaults to DEFAULT_DB_PATH.
        embedder: Optional pre-loaded Embedder (for reuse across calls).
        extractor: Optional pre-loaded EntityExtractor (for reuse across calls).

    Returns:
        IngestResult with counts of what was stored.
    """
    db_path = db_path or DEFAULT_DB_PATH
    prepared = prepare_document(file_path, embedder=embedder, extractor=extractor)
    store = GraphStore(db_path)
    return store_prepared(prepared, store)


def _paper_id(file_path: Path) -> str:
    """Deterministic paper ID from file path."""
    return hashlib.sha1(str(file_path.resolve()).encode()).hexdigest()[:16]


def _slug(name: str) -> str:
    """Deterministic node ID from a name string."""
    return hashlib.sha1(name.lower().strip().encode()).hexdigest()[:12]
