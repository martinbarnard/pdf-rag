"""Kuzu graph schema definition.

Call `create_schema(conn)` with an open kuzu.Connection to initialise all
node and edge tables.  The function is idempotent: it uses IF NOT EXISTS so
it is safe to call on an existing database.
"""

from __future__ import annotations

import kuzu

from pdf_rag.config import EMBEDDING_DIM


# ---------------------------------------------------------------------------
# Node table DDL
# ---------------------------------------------------------------------------

_NODE_TABLES: list[str] = [
    """
    CREATE NODE TABLE IF NOT EXISTS Paper (
        id          STRING,
        title       STRING,
        abstract    STRING,
        year        INT64,
        doi         STRING,
        arxiv_id    STRING,
        file_path   STRING,
        summary     STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Author (
        id              STRING,
        name            STRING,
        canonical_name  STRING,
        orcid           STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Institution (
        id              STRING,
        name            STRING,
        canonical_name  STRING,
        country         STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Venue (
        id      STRING,
        name    STRING,
        type    STRING,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Topic (
        id              STRING,
        name            STRING,
        canonical_name  STRING,
        description     STRING,
        ontology_id     STRING,
        PRIMARY KEY (id)
    )
    """,
    f"""
    CREATE NODE TABLE IF NOT EXISTS Chunk (
        id        STRING,
        text      STRING,
        page      INT64,
        section   STRING,
        embedding FLOAT[{EMBEDDING_DIM}],
        PRIMARY KEY (id)
    )
    """,
]

# ---------------------------------------------------------------------------
# Edge (relationship) table DDL
# ---------------------------------------------------------------------------

_EDGE_TABLES: list[str] = [
    "CREATE REL TABLE IF NOT EXISTS AUTHORED        (FROM Author TO Paper,        MANY_MANY)",
    "CREATE REL TABLE IF NOT EXISTS AFFILIATED_WITH (FROM Author TO Institution,  MANY_MANY)",
    "CREATE REL TABLE IF NOT EXISTS PUBLISHED_IN    (FROM Paper  TO Venue,        MANY_ONE)",
    "CREATE REL TABLE IF NOT EXISTS DISCUSSES       (FROM Paper        TO Topic,       MANY_MANY)",
    "CREATE REL TABLE IF NOT EXISTS CITES           (FROM Paper        TO Paper,       MANY_MANY)",
    "CREATE REL TABLE IF NOT EXISTS HAS_CHUNK       (FROM Paper        TO Chunk,       ONE_MANY)",
    "CREATE REL TABLE IF NOT EXISTS MENTIONS_TOPIC  (FROM Chunk        TO Topic,       MANY_MANY)",
    "CREATE REL TABLE IF NOT EXISTS MENTIONS_AUTHOR (FROM Chunk        TO Author,      MANY_MANY)",
    "CREATE REL TABLE IF NOT EXISTS RELATED_TO      (FROM Topic TO Topic, weight DOUBLE)",
]

# Human-readable lists used by tests to verify completeness.
EXPECTED_NODE_TABLES: list[str] = [
    "Paper",
    "Author",
    "Institution",
    "Venue",
    "Topic",
    "Chunk",
]

EXPECTED_EDGE_TABLES: list[str] = [
    "AUTHORED",
    "AFFILIATED_WITH",
    "PUBLISHED_IN",
    "DISCUSSES",
    "CITES",
    "HAS_CHUNK",
    "MENTIONS_TOPIC",
    "MENTIONS_AUTHOR",
    "RELATED_TO",
]


def create_schema(conn: kuzu.Connection) -> None:
    """Create all node and edge tables if they do not already exist.

    Also runs lightweight migrations (ALTER TABLE ADD COLUMN) for columns
    added after the initial schema so existing databases are upgraded in place.

    Args:
        conn: An open kuzu.Connection to the target database.
    """
    for ddl in _NODE_TABLES:
        conn.execute(ddl)
    for ddl in _EDGE_TABLES:
        conn.execute(ddl)
    _migrate(conn)


def _migrate(conn: kuzu.Connection) -> None:
    """Apply additive migrations to existing databases."""
    _add_column_if_missing(conn, "Paper", "arxiv_id", 'STRING DEFAULT ""')


def _add_column_if_missing(
    conn: kuzu.Connection, table: str, column: str, col_type: str
) -> None:
    """Add a column to a node table if it doesn't already exist."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD {column} {col_type}")
    except Exception:
        pass  # column already exists — kuzu raises on duplicate ADD
