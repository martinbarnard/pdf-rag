"""Author and topic deduplication via fuzzy string matching."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from pdf_rag.config import SIMILARITY_THRESHOLD

# Topics shorter than this (after cleaning) are discarded as noise
_MIN_TOPIC_LEN = 3

# Regex for tokens that are purely numeric or single-character
_JUNK_RE = re.compile(r"^\d+$|^.$")

# Match a parenthetical abbreviation at the end: "Foo Bar (FB)"
_ABBREV_RE = re.compile(r"^(.+?)\s*\(([A-Z][A-Z0-9\-]{1,9})\)\s*$")


def clean_topic(text: str) -> str:
    """Normalise a raw topic string.

    - Collapse whitespace and strip surrounding punctuation/quotes
    - Remove unmatched/truncated opening parentheses (GLiNER truncation artefact)
    - Title-case the result for consistent canonical display
    - Returns an empty string if the result is too short or purely numeric
    """
    # Collapse internal whitespace
    cleaned = re.sub(r"\s+", " ", text).strip()
    # Strip surrounding quotes and punctuation (but not parens yet)
    cleaned = cleaned.strip("\"'.,;:!?")
    # Remove a trailing unmatched '(' and everything after it
    # e.g. "Tiny Recursive Model (Trm" → "Tiny Recursive Model"
    # Only remove if the '(' has no matching ')'
    if cleaned.count("(") > cleaned.count(")"):
        cleaned = re.sub(r"\s*\([^)]*$", "", cleaned).strip()
    # Strip outer non-paren punctuation
    cleaned = cleaned.strip("\"'.,;:!?[]{}")
    if len(cleaned) < _MIN_TOPIC_LEN or _JUNK_RE.match(cleaned):
        return ""
    return cleaned.title()


def _extract_abbrev(topic: str) -> tuple[str, str] | None:
    """If topic is of the form 'Long Name (ABR)', return (long_name, 'ABR').

    Operates on the cleaned, title-cased form.
    e.g. 'Hierarchical Reasoning Model (Hrm)' → ('Hierarchical Reasoning Model', 'HRM')
    """
    m = _ABBREV_RE.match(topic)
    if m:
        return m.group(1).strip(), m.group(2).upper()
    return None


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

    Pipeline:
      1. clean_topic() — whitespace, truncated parens, title-casing, junk filter
      2. Fuzzy clustering — merge strings above `threshold` similarity
      3. Abbreviation merge — cluster whose canonical *is* the abbreviation of
         another cluster gets folded in (e.g. "HRM" → "Hierarchical Reasoning Model")

    Args:
        topics: Raw topic name strings.
        threshold: Fuzzy similarity ratio (0–1) for step 2.

    Returns:
        List of dicts with keys: canonical_name, variants.
    """
    cleaned = [clean_topic(t) for t in topics]
    cleaned = [t for t in cleaned if t]
    clusters = _cluster_strings(cleaned, threshold)
    return _merge_abbreviations(clusters)


def _cluster_strings(strings: list[str], threshold: float) -> list[dict]:
    """Group strings into clusters by fuzzy similarity."""
    if not strings:
        return []

    normalised = [s.strip().lower() for s in strings]
    clusters: list[list[str]] = []

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
        canonical = max(cluster, key=len)
        result.append({"canonical_name": canonical, "variants": cluster})
    return result


def _merge_abbreviations(clusters: list[dict]) -> list[dict]:
    """Merge clusters where one canonical is the abbreviation of another.

    For each cluster whose canonical matches the pattern "Long Name (ABR)",
    extract ABR and look for other clusters whose canonical *equals* ABR
    (case-insensitive).  Fold the abbreviation cluster into the expansion.

    Also handles the reverse: if a bare abbreviation cluster exists and
    another cluster's canonical starts with words whose initials spell that
    abbreviation, merge them.
    """
    if len(clusters) <= 1:
        return clusters

    # Build index: uppercased canonical → cluster index
    upper_index: dict[str, int] = {
        c["canonical_name"].upper(): i for i, c in enumerate(clusters)
    }

    # Build abbreviation map: expansion_idx → abbreviation string
    # from "Long Name (ABR)" patterns
    abbrev_map: dict[int, str] = {}
    for i, c in enumerate(clusters):
        parsed = _extract_abbrev(c["canonical_name"])
        if parsed:
            _long, abbr = parsed
            abbrev_map[i] = abbr

    merged_into: dict[int, int] = {}  # child_idx → parent_idx

    for exp_idx, abbr in abbrev_map.items():
        # Find a cluster whose canonical IS this abbreviation
        abbr_idx = upper_index.get(abbr)
        if abbr_idx is not None and abbr_idx != exp_idx:
            # Merge the bare-abbreviation cluster into the expansion cluster
            merged_into[abbr_idx] = exp_idx

    # Also do initialism matching: if bare cluster "HRM" matches initials of expansion
    for i, c in enumerate(clusters):
        if i in merged_into:
            continue
        name = c["canonical_name"]
        # Only consider short all-caps-looking strings (2-6 chars) as potential abbreviations
        if not (2 <= len(name) <= 6 and name.replace("-", "").isalpha()):
            continue
        abbr_upper = name.upper()
        for j, other in enumerate(clusters):
            if i == j or j in merged_into:
                continue
            # Check if the initials of the other cluster's canonical spell this abbreviation
            words = other["canonical_name"].split()
            initials = "".join(w[0] for w in words if w[0].isalpha()).upper()
            if initials == abbr_upper:
                merged_into[i] = j
                break

    # Apply merges
    result = []
    for i, c in enumerate(clusters):
        parent = merged_into.get(i)
        if parent is not None:
            # Add our variants into the parent
            clusters[parent]["variants"].extend(c["variants"])
        else:
            result.append(c)

    # Recompute canonicals after merging (longest variant wins)
    for c in result:
        c["canonical_name"] = max(c["variants"], key=len)

    return result
