"""Tests for GraphStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_rag.graph.store import GraphStore


class TestGraphStoreInit:
    def test_instantiation(self, tmp_path: Path) -> None:
        store = GraphStore(tmp_path / "store_db")
        assert store is not None

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "store.db"
        GraphStore(db_path)
        assert db_path.parent.exists()

    def test_has_expected_methods(self, tmp_path: Path) -> None:
        store = GraphStore(tmp_path / "methods_db")
        for method in (
            "add_paper", "add_author", "add_topic", "add_chunk",
            "link_author_paper", "link_paper_topic", "link_chunk_topic",
        ):
            assert callable(getattr(store, method, None))


class TestAddPaper:
    def test_add_paper_can_be_queried_back(self, tmp_db: GraphStore) -> None:
        tmp_db.add_paper(
            id="p1", title="Graph RAG", abstract="An abstract.", year=2024,
            doi="10.1234/x", file_path="/tmp/paper.pdf",
        )
        result = tmp_db.execute("MATCH (p:Paper {id: 'p1'}) RETURN p.title")
        assert result.has_next()
        assert result.get_next()[0] == "Graph RAG"

    def test_add_paper_idempotent(self, tmp_db: GraphStore) -> None:
        for _ in range(2):
            tmp_db.add_paper(id="p2", title="Dupe Paper")
        result = tmp_db.execute("MATCH (p:Paper {id: 'p2'}) RETURN count(p)")
        assert result.get_next()[0] == 1

    def test_add_paper_optional_fields_default(self, tmp_db: GraphStore) -> None:
        tmp_db.add_paper(id="p3", title="Minimal")
        result = tmp_db.execute("MATCH (p:Paper {id: 'p3'}) RETURN p.year, p.doi")
        row = result.get_next()
        assert row[0] == 0
        assert row[1] == ""


class TestAddAuthor:
    def test_add_author_can_be_queried_back(self, tmp_db: GraphStore) -> None:
        tmp_db.add_author(id="a1", name="Alice Smith", canonical_name="Alice Smith")
        result = tmp_db.execute("MATCH (a:Author {id: 'a1'}) RETURN a.name")
        assert result.get_next()[0] == "Alice Smith"

    def test_add_author_idempotent(self, tmp_db: GraphStore) -> None:
        for _ in range(2):
            tmp_db.add_author(id="a2", name="Bob")
        result = tmp_db.execute("MATCH (a:Author {id: 'a2'}) RETURN count(a)")
        assert result.get_next()[0] == 1


class TestAddTopic:
    def test_add_topic_can_be_queried_back(self, tmp_db: GraphStore) -> None:
        tmp_db.add_topic(id="t1", name="graph neural networks", canonical_name="Graph Neural Networks")
        result = tmp_db.execute("MATCH (t:Topic {id: 't1'}) RETURN t.canonical_name")
        assert result.get_next()[0] == "Graph Neural Networks"

    def test_add_topic_idempotent(self, tmp_db: GraphStore) -> None:
        for _ in range(2):
            tmp_db.add_topic(id="t2", name="rag")
        result = tmp_db.execute("MATCH (t:Topic {id: 't2'}) RETURN count(t)")
        assert result.get_next()[0] == 1


class TestAddChunk:
    def test_add_chunk_without_embedding(self, tmp_db: GraphStore) -> None:
        tmp_db.add_chunk(id="c1", text="Some chunk text.", section="Introduction")
        result = tmp_db.execute("MATCH (c:Chunk {id: 'c1'}) RETURN c.text, c.section")
        row = result.get_next()
        assert row[0] == "Some chunk text."
        assert row[1] == "Introduction"

    def test_add_chunk_with_embedding(self, tmp_db: GraphStore) -> None:
        embedding = [0.1, 0.2, 0.3, 0.4]
        tmp_db.add_chunk(id="c2", text="Embedded chunk.", section="Methods", embedding=embedding)
        result = tmp_db.execute("MATCH (c:Chunk {id: 'c2'}) RETURN c.embedding")
        row = result.get_next()
        assert row[0] is not None
        assert len(row[0]) == 4

    def test_add_chunk_idempotent(self, tmp_db: GraphStore) -> None:
        for _ in range(2):
            tmp_db.add_chunk(id="c3", text="Dupe chunk.")
        result = tmp_db.execute("MATCH (c:Chunk {id: 'c3'}) RETURN count(c)")
        assert result.get_next()[0] == 1


class TestEdgeWriters:
    def test_link_author_paper(self, tmp_db: GraphStore) -> None:
        tmp_db.add_author(id="a1", name="Alice")
        tmp_db.add_paper(id="p1", title="Paper")
        tmp_db.link_author_paper("a1", "p1")
        result = tmp_db.execute(
            "MATCH (a:Author {id: 'a1'})-[:AUTHORED]->(p:Paper {id: 'p1'}) RETURN p.title"
        )
        assert result.has_next()

    def test_link_paper_topic(self, tmp_db: GraphStore) -> None:
        tmp_db.add_paper(id="p1", title="Paper")
        tmp_db.add_topic(id="t1", name="rag")
        tmp_db.link_paper_topic("p1", "t1")
        result = tmp_db.execute(
            "MATCH (p:Paper {id: 'p1'})-[:DISCUSSES]->(t:Topic {id: 't1'}) RETURN t.name"
        )
        assert result.has_next()

    def test_link_chunk_topic(self, tmp_db: GraphStore) -> None:
        tmp_db.add_chunk(id="c1", text="text")
        tmp_db.add_topic(id="t1", name="rag")
        tmp_db.link_chunk_topic("c1", "t1")
        result = tmp_db.execute(
            "MATCH (c:Chunk {id: 'c1'})-[:MENTIONS_TOPIC]->(t:Topic {id: 't1'}) RETURN t.name"
        )
        assert result.has_next()

    def test_link_author_paper_idempotent(self, tmp_db: GraphStore) -> None:
        tmp_db.add_author(id="a1", name="Alice")
        tmp_db.add_paper(id="p1", title="Paper")
        tmp_db.link_author_paper("a1", "p1")
        tmp_db.link_author_paper("a1", "p1")  # second call should not raise
        result = tmp_db.execute(
            "MATCH (a:Author {id: 'a1'})-[:AUTHORED]->(p:Paper {id: 'p1'}) RETURN count(*)"
        )
        assert result.get_next()[0] >= 1
