"""Tests for graph schema creation."""

from __future__ import annotations

from pathlib import Path

import kuzu
import pytest

from pdf_rag.graph.schema import (
    EXPECTED_EDGE_TABLES,
    EXPECTED_NODE_TABLES,
    create_schema,
)


def _table_names(conn: kuzu.Connection) -> set[str]:
    """Return the set of table names present in the database."""
    result = conn.execute("CALL show_tables() RETURN name")
    names: set[str] = set()
    while result.has_next():
        row = result.get_next()
        names.add(row[0])
    return names


class TestCreateSchema:
    def test_runs_without_error_on_fresh_db(self, tmp_path: Path) -> None:
        db = kuzu.Database(str(tmp_path / "fresh"))
        conn = kuzu.Connection(db)
        # Should not raise.
        create_schema(conn)

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling create_schema twice must not raise."""
        db = kuzu.Database(str(tmp_path / "idempotent"))
        conn = kuzu.Connection(db)
        create_schema(conn)
        create_schema(conn)

    def test_all_node_tables_exist(self, tmp_path: Path) -> None:
        db = kuzu.Database(str(tmp_path / "nodes"))
        conn = kuzu.Connection(db)
        create_schema(conn)
        existing = _table_names(conn)
        for table in EXPECTED_NODE_TABLES:
            assert table in existing, f"Node table '{table}' is missing"

    def test_all_edge_tables_exist(self, tmp_path: Path) -> None:
        db = kuzu.Database(str(tmp_path / "edges"))
        conn = kuzu.Connection(db)
        create_schema(conn)
        existing = _table_names(conn)
        for table in EXPECTED_EDGE_TABLES:
            assert table in existing, f"Edge table '{table}' is missing"

    def test_paper_has_arxiv_id_column(self, tmp_path: Path) -> None:
        db = kuzu.Database(str(tmp_path / "arxiv"))
        conn = kuzu.Connection(db)
        create_schema(conn)
        # Insert and read back arxiv_id to confirm the column exists
        conn.execute(
            "CREATE (p:Paper {id: 'a1', title: 'T', abstract: '', year: 0, "
            "doi: '', arxiv_id: '2301.04567', file_path: '', summary: ''})"
        )
        result = conn.execute("MATCH (p:Paper {id: 'a1'}) RETURN p.arxiv_id")
        assert result.get_next()[0] == "2301.04567"

    def test_migration_adds_arxiv_id_to_existing_db(self, tmp_path: Path) -> None:
        """create_schema on a DB without arxiv_id should add it silently."""
        db = kuzu.Database(str(tmp_path / "migrate"))
        conn = kuzu.Connection(db)
        # Create Paper table without arxiv_id (old schema)
        conn.execute(
            "CREATE NODE TABLE IF NOT EXISTS Paper "
            "(id STRING, title STRING, abstract STRING, year INT64, "
            "doi STRING, file_path STRING, summary STRING, PRIMARY KEY (id))"
        )
        # Running create_schema should apply the migration
        create_schema(conn)
        conn.execute(
            "CREATE (p:Paper {id: 'b1', title: 'T', abstract: '', year: 0, "
            "doi: '', arxiv_id: '2401.00001', file_path: '', summary: ''})"
        )
        result = conn.execute("MATCH (p:Paper {id: 'b1'}) RETURN p.arxiv_id")
        assert result.get_next()[0] == "2401.00001"
