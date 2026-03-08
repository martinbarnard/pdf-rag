"""Author and topic deduplication via fuzzy string matching."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from pdf_rag.config import SIMILARITY_THRESHOLD

# Topics shorter than this (after cleaning) are discarded as noise
_MIN_TOPIC_LEN = 3

# Regex for tokens that are purely numeric or single characters
_JUNK_RE = re.compile(r"^\d+$|^.$")


def clean_topic(text: str) -> str:
    """Normalise a raw topic string.

    - Collapse whitespace and strip surrounding punctuation/quotes
    - Title-case the result for consistent canonical display
    - Returns an empty string if the result is too short or purely numeric
    """
    # Collapse internal whitespace, strip surrounding junk
    cleaned = re.sub(r"\s+", " ", text).strip().strip("\"'.,;:!?()[]{}")
    if len(cleaned) < _MIN_TOPIC_LEN or _JUNK_RE.match(cleaned):
        return ""
    return cleaned.title()


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
    threshold: float = 0.80,
) -> list[dict]:
    """Clean, deduplicate, and normalise topic/concept strings.

    Applies clean_topic() first (whitespace, punctuation, title-casing), then
    clusters similar strings with fuzzy matching.  Uses a slightly lower
    threshold than authors (0.80 vs 0.85) because short phrases match less
    precisely.

    Args:
        topics: Raw topic name strings.
        threshold: Similarity ratio (0–1) above which two topics are merged.

    Returns:
        List of dicts with keys: canonical_name, variants.
    """
    cleaned = [clean_topic(t) for t in topics]
    cleaned = [t for t in cleaned if t]  # drop empty after cleaning
    return _cluster_strings(cleaned, threshold)


def _cluster_strings(strings: list[str], threshold: float) -> list[dict]:
    """Group strings into clusters by fuzzy similarity and return canonical forms."""
    if not strings:
        return []

    normalised = [s.strip().lower() for s in strings]
    clusters: list[list[str]] = []  # each cluster holds cleaned strings

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
