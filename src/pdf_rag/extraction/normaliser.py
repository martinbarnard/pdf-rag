"""Author and topic deduplication via fuzzy string matching."""

from __future__ import annotations

from rapidfuzz import fuzz

from pdf_rag.config import SIMILARITY_THRESHOLD


def normalise_authors(
    names: list[str],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Deduplicate author name variants using fuzzy matching.

    Merges names above `threshold` similarity into a single canonical entry,
    choosing the longest variant as the canonical name.

    Args:
        names: Raw author name strings.
        threshold: Similarity ratio (0–1) above which two names are merged.

    Returns:
        List of dicts with keys: canonical_name, variants.
    """
    return _cluster_strings(names, threshold)


def normalise_topics(
    topics: list[str],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Deduplicate topic/concept strings using fuzzy matching.

    Args:
        topics: Raw topic name strings.
        threshold: Similarity ratio (0–1) above which two topics are merged.

    Returns:
        List of dicts with keys: canonical_name, variants.
    """
    return _cluster_strings(topics, threshold)


def _cluster_strings(strings: list[str], threshold: float) -> list[dict]:
    """Group strings into clusters by fuzzy similarity and return canonical forms."""
    if not strings:
        return []

    # Normalise to lowercase for comparison, keep originals
    normalised = [s.strip().lower() for s in strings]
    clusters: list[list[str]] = []  # each cluster holds original strings

    for original, norm in zip(strings, normalised):
        placed = False
        for cluster in clusters:
            representative = cluster[0].strip().lower()
            score = fuzz.ratio(norm, representative) / 100.0
            if score >= threshold:
                cluster.append(original)
                placed = True
                break
        if not placed:
            clusters.append([original])

    result = []
    for cluster in clusters:
        # Pick the longest variant as canonical (most complete name)
        canonical = max(cluster, key=len)
        result.append({"canonical_name": canonical, "variants": cluster})

    return result
