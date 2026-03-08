"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import kuzu
import pytest

from pdf_rag.graph.schema import create_schema
from pdf_rag.graph.store import GraphStore


@pytest.fixture()
def tmp_db(tmp_path: Path) -> GraphStore:
    """Return a GraphStore backed by a fresh temporary database."""
    return GraphStore(tmp_path / "test_graph.db")


@pytest.fixture()
def tmp_conn(tmp_path: Path) -> kuzu.Connection:
    """Return a raw kuzu.Connection for schema-level tests."""
    db_path = tmp_path / "schema_test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    create_schema(conn)
    return conn


@pytest.fixture()
def sample_text() -> str:
    """A short scientific paper abstract for use in ingestion tests."""
    return (
        "We present a novel graph-based retrieval-augmented generation (RAG) "
        "framework for scientific literature. Our approach combines knowledge "
        "graphs with dense vector retrieval to improve factual grounding of "
        "large language model responses. Experiments on three benchmark datasets "
        "demonstrate state-of-the-art performance, with a 12% improvement in "
        "answer accuracy over baseline RAG systems. The framework is evaluated "
        "on PubMed, ArXiv, and Semantic Scholar corpora."
    )
