"""Kuzu graph store — read/write operations."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import kuzu

from pdf_rag.graph.schema import create_schema

# ---------------------------------------------------------------------------
# Process-level Database singleton
#
# kuzu only allows ONE kuzu.Database object per database path per process.
# Opening a second one raises "unordered_map::at" (IndexError).  Multiple
# kuzu.Connection objects on the same Database are fine, so we share one
# Database and hand each GraphStore its own Connection.
# ---------------------------------------------------------------------------

_db_instances: dict[str, kuzu.Database] = {}
_db_lock = threading.Lock()


def _get_database(db_path: Path) -> kuzu.Database:
    """Return the shared kuzu.Database for the given path, creating it if needed.

    If the initial open fails (e.g. stale WAL from a previous crash), the WAL
    file is removed and the open is retried once with a clean slate.
    """
    key = str(db_path.resolve())
    with _db_lock:
        if key not in _db_instances:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                _db_instances[key] = kuzu.Database(str(db_path))
            except (IndexError, RuntimeError):
                # Stale WAL / corrupted metadata — remove WAL and retry.
                wal = db_path.with_suffix(db_path.suffix + ".wal")
                if wal.exists():
                    wal.unlink()
                _db_instances[key] = kuzu.Database(str(db_path))
        return _db_instances[key]


def _release_database(db_path: Path) -> None:
    """Remove the cached Database for *db_path* (test teardown only).

    After calling this, the next GraphStore opened on the same path will create
    a fresh kuzu.Database.  Do NOT call this in production code.
    """
    key = str(db_path.resolve())
    with _db_lock:
        _db_instances.pop(key, None)


class GraphStore:
    """Thin wrapper around a kuzu database that enforces the project schema.

    Multiple GraphStore instances for the same path safely share one
    kuzu.Database object (process singleton) and each get their own
    kuzu.Connection.
    """

    def __init__(self, db_path: Path | str) -> None:
        db_path = Path(db_path)
        self._db = _get_database(db_path)
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
        arxiv_id: str = "",
        file_path: str = "",
        summary: str = "",
    ) -> None:
        """Upsert a Paper node."""
        self._conn.execute(
            """
            MERGE (p:Paper {id: $id})
            ON CREATE SET p.title = $title, p.abstract = $abstract,
                          p.year = $year, p.doi = $doi,
                          p.arxiv_id = $arxiv_id,
                          p.file_path = $file_path, p.summary = $summary
            """,
            {"id": id, "title": title, "abstract": abstract,
             "year": year, "doi": doi, "arxiv_id": arxiv_id,
             "file_path": file_path, "summary": summary},
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

    def link_related_topics(self, topic_id_a: str, topic_id_b: str, weight: float = 1.0) -> None:
        """Create a RELATED_TO edge between two Topic nodes with a weight."""
        self._conn.execute(
            """
            MATCH (a:Topic {id: $aid}), (b:Topic {id: $bid})
            MERGE (a)-[r:RELATED_TO]->(b)
            ON CREATE SET r.weight = $w
            """,
            {"aid": topic_id_a, "bid": topic_id_b, "w": weight},
        )

    # ------------------------------------------------------------------
    # Graph traversal queries
    # ------------------------------------------------------------------

    def papers_by_author(self, author_id: str) -> list[dict]:
        """Return all papers authored by the given author."""
        result = self._conn.execute(
            """
            MATCH (a:Author {id: $aid})-[:AUTHORED]->(p:Paper)
            RETURN p.id, p.title, p.year
            """,
            {"aid": author_id},
        )
        return self._collect(result, ["id", "title", "year"])

    def papers_by_topic(self, topic_id: str) -> list[dict]:
        """Return all papers that discuss the given topic."""
        result = self._conn.execute(
            """
            MATCH (p:Paper)-[:DISCUSSES]->(t:Topic {id: $tid})
            RETURN p.id, p.title, p.year
            """,
            {"tid": topic_id},
        )
        return self._collect(result, ["id", "title", "year"])

    def related_topics(self, topic_id: str) -> list[dict]:
        """Return topics related to the given topic, ordered by weight desc."""
        result = self._conn.execute(
            """
            MATCH (a:Topic {id: $tid})-[r:RELATED_TO]->(b:Topic)
            RETURN b.id, b.canonical_name, r.weight
            ORDER BY r.weight DESC
            """,
            {"tid": topic_id},
        )
        return self._collect(result, ["id", "canonical_name", "weight"])

    def coauthor_network(self, author_id: str) -> list[dict]:
        """Return all co-authors of the given author (authors sharing at least one paper)."""
        result = self._conn.execute(
            """
            MATCH (a:Author {id: $aid})-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(b:Author)
            WHERE b.id <> $aid
            RETURN DISTINCT b.id, b.canonical_name
            """,
            {"aid": author_id},
        )
        return self._collect(result, ["id", "canonical_name"])

    def citing_papers(self, paper_id: str) -> list[dict]:
        """Return all papers that cite the given paper."""
        result = self._conn.execute(
            """
            MATCH (citing:Paper)-[:CITES]->(p:Paper {id: $pid})
            RETURN citing.id, citing.title, citing.year
            """,
            {"pid": paper_id},
        )
        return self._collect(result, ["id", "title", "year"])

    def cited_papers(self, paper_id: str) -> list[dict]:
        """Return all papers cited by the given paper."""
        result = self._conn.execute(
            """
            MATCH (p:Paper {id: $pid})-[:CITES]->(cited:Paper)
            RETURN cited.id, cited.title, cited.year
            """,
            {"pid": paper_id},
        )
        return self._collect(result, ["id", "title", "year"])

    @staticmethod
    def _collect(result, keys: list[str]) -> list[dict]:
        """Convert a kuzu QueryResult into a list of dicts."""
        rows = []
        while result.has_next():
            row = result.get_next()
            rows.append(dict(zip(keys, row)))
        return rows

    def paper_context(self, paper_id: str) -> dict:
        """Return metadata needed to build an arXiv search for a paper.

        Returns a dict with keys:
            arxiv_id, title, topics (list[str]), authors (list[str]),
            chunk_embeddings (list[list[float]])
        Returns None if the paper is not found.
        """
        r = self._conn.execute(
            "MATCH (p:Paper {id: $id}) RETURN p.title, p.arxiv_id",
            {"id": paper_id},
        )
        if not r.has_next():
            return {}
        row = r.get_next()
        title, arxiv_id = row[0], row[1] or ""

        tr = self._conn.execute(
            "MATCH (p:Paper {id: $id})-[:DISCUSSES]->(t:Topic) RETURN t.canonical_name",
            {"id": paper_id},
        )
        topics = [r2.get_next()[0] for r2 in iter(lambda: tr if tr.has_next() else None, None)]
        topics = []
        while tr.has_next():
            topics.append(tr.get_next()[0])

        ar = self._conn.execute(
            "MATCH (a:Author)-[:AUTHORED]->(p:Paper {id: $id}) RETURN a.canonical_name",
            {"id": paper_id},
        )
        authors: list[str] = []
        while ar.has_next():
            authors.append(ar.get_next()[0])

        cr = self._conn.execute(
            """
            MATCH (p:Paper {id: $id})-[:HAS_CHUNK]->(c:Chunk)
            WHERE c.embedding IS NOT NULL
            RETURN c.embedding
            LIMIT 20
            """,
            {"id": paper_id},
        )
        embeddings: list[list[float]] = []
        while cr.has_next():
            emb = cr.get_next()[0]
            if emb is not None:
                embeddings.append(list(emb))

        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "topics": topics,
            "authors": authors,
            "chunk_embeddings": embeddings,
        }

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    def search_similar_chunks(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """Find the top-k most similar Chunks by cosine similarity.

        Only Chunks that have a non-null embedding are considered.

        Args:
            query_embedding: Query vector (must match EMBEDDING_DIM).
            top_k: Number of results to return.

        Returns:
            List of dicts with keys: id, text, section, score.
            Ordered by descending similarity score.
        """
        result = self._conn.execute(
            """
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL
            WITH c, array_cosine_similarity(c.embedding, $q) AS score
            ORDER BY score DESC
            LIMIT $k
            RETURN c.id, c.text, c.section, score
            """,
            {"q": query_embedding, "k": top_k},
        )
        rows = []
        while result.has_next():
            row = result.get_next()
            rows.append({"id": row[0], "text": row[1], "section": row[2], "score": float(row[3])})
        return rows

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute an arbitrary Cypher query and return the result."""
        if params:
            return self._conn.execute(query, params)
        return self._conn.execute(query)
