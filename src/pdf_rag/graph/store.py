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
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(db_path))
        self._conn = kuzu.Connection(self._db)
        create_schema(self._conn)

    # ------------------------------------------------------------------
    # Node insertion
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
        """Upsert a Paper node."""
        self._conn.execute(
            """
            MERGE (p:Paper {id: $id})
            ON CREATE SET p.title = $title, p.abstract = $abstract,
                          p.year = $year, p.doi = $doi,
                          p.file_path = $file_path, p.summary = $summary
            """,
            {"id": id, "title": title, "abstract": abstract,
             "year": year, "doi": doi, "file_path": file_path, "summary": summary},
        )

    def add_author(
        self,
        id: str,
        name: str,
        canonical_name: str = "",
        orcid: str = "",
    ) -> None:
        """Upsert an Author node."""
        self._conn.execute(
            """
            MERGE (a:Author {id: $id})
            ON CREATE SET a.name = $name, a.canonical_name = $canonical_name,
                          a.orcid = $orcid
            """,
            {"id": id, "name": name, "canonical_name": canonical_name, "orcid": orcid},
        )

    def add_institution(
        self,
        id: str,
        name: str,
        canonical_name: str = "",
        country: str = "",
    ) -> None:
        """Upsert an Institution node."""
        self._conn.execute(
            """
            MERGE (i:Institution {id: $id})
            ON CREATE SET i.name = $name, i.canonical_name = $canonical_name,
                          i.country = $country
            """,
            {"id": id, "name": name, "canonical_name": canonical_name, "country": country},
        )

    def add_venue(self, id: str, name: str, type: str = "") -> None:
        """Upsert a Venue node."""
        self._conn.execute(
            """
            MERGE (v:Venue {id: $id})
            ON CREATE SET v.name = $name, v.type = $type
            """,
            {"id": id, "name": name, "type": type},
        )

    def add_topic(
        self,
        id: str,
        name: str,
        canonical_name: str = "",
        description: str = "",
        ontology_id: str = "",
    ) -> None:
        """Upsert a Topic node."""
        self._conn.execute(
            """
            MERGE (t:Topic {id: $id})
            ON CREATE SET t.name = $name, t.canonical_name = $canonical_name,
                          t.description = $description, t.ontology_id = $ontology_id
            """,
            {"id": id, "name": name, "canonical_name": canonical_name,
             "description": description, "ontology_id": ontology_id},
        )

    def add_chunk(
        self,
        id: str,
        text: str,
        page: int = 0,
        section: str = "",
        embedding: list[float] | None = None,
    ) -> None:
        """Upsert a Chunk node, optionally with an embedding vector."""
        self._conn.execute(
            """
            MERGE (c:Chunk {id: $id})
            ON CREATE SET c.text = $text, c.page = $page,
                          c.section = $section, c.embedding = $embedding
            """,
            {"id": id, "text": text, "page": page,
             "section": section, "embedding": embedding},
        )

    # ------------------------------------------------------------------
    # Edge insertion
    # ------------------------------------------------------------------

    def link_author_paper(self, author_id: str, paper_id: str) -> None:
        """Create an AUTHORED edge from Author to Paper (idempotent)."""
        self._conn.execute(
            """
            MATCH (a:Author {id: $aid}), (p:Paper {id: $pid})
            MERGE (a)-[:AUTHORED]->(p)
            """,
            {"aid": author_id, "pid": paper_id},
        )

    def link_paper_topic(self, paper_id: str, topic_id: str) -> None:
        """Create a DISCUSSES edge from Paper to Topic (idempotent)."""
        self._conn.execute(
            """
            MATCH (p:Paper {id: $pid}), (t:Topic {id: $tid})
            MERGE (p)-[:DISCUSSES]->(t)
            """,
            {"pid": paper_id, "tid": topic_id},
        )

    def link_chunk_topic(self, chunk_id: str, topic_id: str) -> None:
        """Create a MENTIONS_TOPIC edge from Chunk to Topic (idempotent)."""
        self._conn.execute(
            """
            MATCH (c:Chunk {id: $cid}), (t:Topic {id: $tid})
            MERGE (c)-[:MENTIONS_TOPIC]->(t)
            """,
            {"cid": chunk_id, "tid": topic_id},
        )

    def link_paper_chunk(self, paper_id: str, chunk_id: str) -> None:
        """Create a HAS_CHUNK edge from Paper to Chunk (idempotent)."""
        self._conn.execute(
            """
            MATCH (p:Paper {id: $pid}), (c:Chunk {id: $cid})
            MERGE (p)-[:HAS_CHUNK]->(c)
            """,
            {"pid": paper_id, "cid": chunk_id},
        )

    def link_paper_cites(self, citing_id: str, cited_id: str) -> None:
        """Create a CITES edge between two Paper nodes (idempotent)."""
        self._conn.execute(
            """
            MATCH (a:Paper {id: $aid}), (b:Paper {id: $bid})
            MERGE (a)-[:CITES]->(b)
            """,
            {"aid": citing_id, "bid": cited_id},
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute an arbitrary Cypher query and return the result."""
        if params:
            return self._conn.execute(query, params)
        return self._conn.execute(query)
