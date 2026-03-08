"""Tests for GraphStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_rag.graph.store import GraphStore


class TestGraphStoreInit:
    def test_instantiation(self, tmp_path: Path) -> None:
        """GraphStore must be instantiatable with a fresh tmp path."""
        store = GraphStore(tmp_path / "store_db")
        assert store is not None

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """GraphStore must create missing parent directories."""
        db_path = tmp_path / "nested" / "store.db"
        GraphStore(db_path)
        assert db_path.parent.exists()

    def test_has_expected_methods(self, tmp_path: Path) -> None:
        store = GraphStore(tmp_path / "methods_db")
        for method in (
            "add_paper",
            "add_author",
            "add_topic",
            "add_chunk",
            "link_author_paper",
            "link_paper_topic",
            "link_chunk_topic",
        ):
            assert callable(getattr(store, method, None)), (
                f"GraphStore is missing method '{method}'"
            )


class TestAddPaper:
    def test_add_paper_raises_not_implemented(self, tmp_path: Path) -> None:
        """add_paper is a stub; must raise NotImplementedError until implemented."""
        store = GraphStore(tmp_path / "paper_db")
        with pytest.raises(NotImplementedError):
            store.add_paper(
                id="paper-001",
                title="Graph RAG for Scientific Literature",
                abstract="An abstract.",
                year=2024,
                doi="10.1234/example",
                file_path="/tmp/paper.pdf",
            )

    # ------------------------------------------------------------------ #
    # This test is intentionally written TDD-style: it will pass once     #
    # add_paper is implemented.  For now it is skipped.                   #
    # ------------------------------------------------------------------ #
    @pytest.mark.skip(reason="add_paper not yet implemented")
    def test_add_paper_can_be_queried_back(self, tmp_path: Path) -> None:
        store = GraphStore(tmp_path / "query_db")
        store.add_paper(
            id="paper-001",
            title="Graph RAG for Scientific Literature",
            abstract="An abstract.",
            year=2024,
        )
        result = store.execute(
            "MATCH (p:Paper {id: $id}) RETURN p.title",
            {"id": "paper-001"},
        )
        assert result.has_next()
        row = result.get_next()
        assert row[0] == "Graph RAG for Scientific Literature"
