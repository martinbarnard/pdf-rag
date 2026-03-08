"""Tests for the ingestion pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdf_rag.pipeline import IngestResult, ingest_document


@pytest.fixture(scope="session")
def shared_embedder():
    """Single Embedder instance shared across all pipeline tests to avoid OOM."""
    from pdf_rag.ingestion.embedder import Embedder
    return Embedder()


@pytest.fixture(scope="session")
def shared_extractor():
    """Single EntityExtractor instance shared across all pipeline tests."""
    from pdf_rag.extraction.entities import EntityExtractor
    return EntityExtractor()


@pytest.fixture
def md_file(tmp_path) -> Path:
    f = tmp_path / "paper.md"
    f.write_text(
        "# Attention Is All You Need\n\n"
        "## Abstract\n\nWe propose a new network architecture, the Transformer.\n\n"
        "## Introduction\n\nRecurrent models have long dominated sequence modelling.\n\n"
        "## References\n\nVaswani et al. (2017). Attention is all you need. NeurIPS.\n"
    )
    return f


class TestIngestResult:
    def test_has_expected_fields(self) -> None:
        r = IngestResult(
            file_path=Path("paper.pdf"),
            paper_id="p1",
            chunk_count=5,
            entity_count=3,
            citation_count=2,
        )
        assert r.paper_id == "p1"
        assert r.chunk_count == 5


class TestIngestDocument:
    def test_returns_ingest_result(self, md_file, tmp_path, shared_embedder, shared_extractor) -> None:
        result = ingest_document(md_file, db_path=tmp_path / "t1.db", embedder=shared_embedder, extractor=shared_extractor)
        assert isinstance(result, IngestResult)

    def test_paper_id_is_string(self, md_file, tmp_path, shared_embedder, shared_extractor) -> None:
        result = ingest_document(md_file, db_path=tmp_path / "t2.db", embedder=shared_embedder, extractor=shared_extractor)
        assert isinstance(result.paper_id, str)
        assert len(result.paper_id) > 0

    def test_chunks_produced(self, md_file, tmp_path, shared_embedder, shared_extractor) -> None:
        result = ingest_document(md_file, db_path=tmp_path / "t3.db", embedder=shared_embedder, extractor=shared_extractor)
        assert result.chunk_count > 0

    def test_file_path_preserved(self, md_file, tmp_path, shared_embedder, shared_extractor) -> None:
        result = ingest_document(md_file, db_path=tmp_path / "t4.db", embedder=shared_embedder, extractor=shared_extractor)
        assert result.file_path == md_file

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ingest_document(tmp_path / "missing.md", db_path=tmp_path / "test.db")

    def test_unsupported_format_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "file.xyz"
        bad.write_text("nope")
        with pytest.raises(ValueError, match="Unsupported"):
            ingest_document(bad, db_path=tmp_path / "test.db")

    def test_paper_stored_in_graph(self, md_file, tmp_path, shared_embedder, shared_extractor) -> None:
        db_path = tmp_path / "t5.db"
        result = ingest_document(md_file, db_path=db_path, embedder=shared_embedder, extractor=shared_extractor)
        from pdf_rag.graph.store import GraphStore
        store = GraphStore(db_path)
        r = store.execute("MATCH (p:Paper {id: $id}) RETURN p.title", {"id": result.paper_id})
        assert r.has_next()

    def test_chunks_stored_in_graph(self, md_file, tmp_path, shared_embedder, shared_extractor) -> None:
        db_path = tmp_path / "t6.db"
        result = ingest_document(md_file, db_path=db_path, embedder=shared_embedder, extractor=shared_extractor)
        from pdf_rag.graph.store import GraphStore
        store = GraphStore(db_path)
        r = store.execute(
            "MATCH (p:Paper {id: $pid})-[:HAS_CHUNK]->(c:Chunk) RETURN count(c)",
            {"pid": result.paper_id},
        )
        assert r.get_next()[0] == result.chunk_count

    def test_idempotent_reingest(self, md_file, tmp_path, shared_embedder, shared_extractor) -> None:
        db_path = tmp_path / "t7.db"
        r1 = ingest_document(md_file, db_path=db_path, embedder=shared_embedder, extractor=shared_extractor)
        r2 = ingest_document(md_file, db_path=db_path, embedder=shared_embedder, extractor=shared_extractor)
        assert r1.paper_id == r2.paper_id
        from pdf_rag.graph.store import GraphStore
        store = GraphStore(db_path)
        r = store.execute("MATCH (p:Paper {id: $id}) RETURN count(p)", {"id": r1.paper_id})
        assert r.get_next()[0] == 1
