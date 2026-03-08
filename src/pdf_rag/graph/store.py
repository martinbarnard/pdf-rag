"""Kuzu graph store — read/write operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import kuzu

from pdf_rag.graph.schema import create_schema


class GraphStore:
    """Thin wrapper around a kuzu database that enforces the project schema."""

    def __init__(self, db_path: Path | str) -> None:
        db_path = Path(db_path)
        # kuzu manages its own storage files; only the parent directory needs
        # to exist.  Do NOT create db_path itself as a directory.
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(db_path))
        self._conn = kuzu.Connection(self._db)
        create_schema(self._conn)

    # ------------------------------------------------------------------
    # Node insertion stubs
    # ------------------------------------------------------------------

    def add_paper(
        self,
        id: str,
        title: str,
        abstract: str = "",
        year: int = 0,
        doi: str = "",
        file_path: str = "",
        summary: str = "",
    ) -> None:
        """Insert a Paper node; no-op if the id already exists."""
        raise NotImplementedError

    def add_author(
        self,
        id: str,
        name: str,
        canonical_name: str = "",
        orcid: str = "",
    ) -> None:
        """Insert an Author node; no-op if the id already exists."""
        raise NotImplementedError

    def add_topic(
        self,
        id: str,
        name: str,
        canonical_name: str = "",
        description: str = "",
        ontology_id: str = "",
    ) -> None:
        """Insert a Topic node; no-op if the id already exists."""
        raise NotImplementedError

    def add_chunk(
        self,
        id: str,
        text: str,
        page: int = 0,
        section: str = "",
    ) -> None:
        """Insert a Chunk node; no-op if the id already exists."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Edge insertion stubs
    # ------------------------------------------------------------------

    def link_author_paper(self, author_id: str, paper_id: str) -> None:
        """Create an AUTHORED edge from Author to Paper."""
        raise NotImplementedError

    def link_paper_topic(self, paper_id: str, topic_id: str) -> None:
        """Create a DISCUSSES edge from Paper to Topic."""
        raise NotImplementedError

    def link_chunk_topic(self, chunk_id: str, topic_id: str) -> None:
        """Create a MENTIONS_TOPIC edge from Chunk to Topic."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute an arbitrary Cypher query and return the result."""
        if params:
            return self._conn.execute(query, params)
        return self._conn.execute(query)
