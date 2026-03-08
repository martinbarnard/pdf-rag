"""Author and topic deduplication via fuzzy matching."""

from __future__ import annotations

from pdf_rag.config import SIMILARITY_THRESHOLD


def normalise_entities(
    entities: list[dict],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Deduplicate a list of extracted entities using rapidfuzz similarity.

    Entities with a name similarity above `threshold` are merged into a
    single canonical entry.

    Args:
        entities: List of entity dicts (must have a ``text`` key).
        threshold: Minimum similarity score (0–1) for two names to be merged.

    Returns:
        Deduplicated list of entity dicts with an added ``canonical_name`` key.
    """
    raise NotImplementedError
