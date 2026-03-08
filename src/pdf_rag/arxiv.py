"""arXiv API client for finding related papers.

Wraps the arXiv Atom API (https://export.arxiv.org/api/query).
Rate-limited to one request per `min_interval` seconds (arXiv asks for 3s).

Usage::

    client = ArxivClient()

    # Search by keyword terms (uses ti: + abs: fields)
    results = client.search(terms=["transformer", "attention"], max_results=10)

    # Search by known arXiv ID (fetches the paper then its category siblings)
    results = client.search(arxiv_id="2301.04567", max_results=10)

Each result is an ArxivResult dataclass with arxiv_id, title, authors,
abstract, published, categories, pdf_url, and similarity_score (0.0 until
re-ranked by the caller).

Attribution: arXiv.org — see https://arxiv.org/help/api/user-manual
"""

from __future__ import annotations

import math
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

_ATOM_NS  = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"

_ID_RE    = re.compile(r"arxiv\.org/abs/([^v\s]+)")  # extract bare ID from URL


@dataclass
class ArxivResult:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str          # ISO date string e.g. "2023-01-12"
    categories: list[str]
    pdf_url: str
    similarity_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "published": self.published,
            "categories": self.categories,
            "pdf_url": self.pdf_url,
            "similarity_score": self.similarity_score,
        }


class ArxivClient:
    """Thin wrapper around the arXiv Atom query API.

    Args:
        base_url: Base URL for the arXiv API (override for testing).
        min_interval: Minimum seconds between requests (arXiv guideline: 3s).
        timeout: HTTP request timeout in seconds.
    """

    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(
        self,
        base_url: str = BASE_URL,
        min_interval: float = 3.0,
        timeout: float = 15.0,
    ) -> None:
        self._base_url = base_url
        self._min_interval = min_interval
        self._timeout = timeout
        self._last_call: float = 0.0

    def search(
        self,
        terms: list[str] | None = None,
        arxiv_id: str | None = None,
        max_results: int = 10,
    ) -> list[ArxivResult]:
        """Search arXiv and return a list of ArxivResult objects.

        Either `terms` or `arxiv_id` must be provided.

        Args:
            terms: Keyword phrases searched in title + abstract.
            arxiv_id: Fetch by exact arXiv ID (e.g. "2301.04567").
            max_results: Maximum number of results to return.

        Returns:
            List of ArxivResult, ordered by arXiv relevance.
            Empty list on network error or no results.

        Raises:
            ValueError: If neither terms nor arxiv_id is provided.
        """
        if not terms and not arxiv_id:
            raise ValueError("Provide at least one of terms or arxiv_id")

        self._rate_limit()

        if arxiv_id:
            query = f"id_list={arxiv_id}"
        else:
            parts = [
                f"(ti:{t} OR abs:{t})"
                for t in terms  # type: ignore[union-attr]
                if t.strip()
            ]
            query = f"search_query={'+AND+'.join(parts)}&max_results={max_results}"

        url = f"{self._base_url}?{query}&max_results={max_results}"

        try:
            import httpx
            resp = httpx.get(url, timeout=self._timeout)
            resp.raise_for_status()
            return self._parse_atom(resp.text)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Sleep if needed to respect min_interval between API calls."""
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _parse_atom(self, xml_text: str) -> list[ArxivResult]:
        """Parse an arXiv Atom feed and return ArxivResult objects."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        results: list[ArxivResult] = []
        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            arxiv_id = self._extract_id(entry)
            if not arxiv_id:
                continue

            title = (entry.findtext(f"{{{_ATOM_NS}}}title") or "").strip()
            abstract = (entry.findtext(f"{{{_ATOM_NS}}}summary") or "").strip()
            published = (entry.findtext(f"{{{_ATOM_NS}}}published") or "")[:10]

            authors = [
                a.findtext(f"{{{_ATOM_NS}}}name") or ""
                for a in entry.findall(f"{{{_ATOM_NS}}}author")
            ]
            authors = [a for a in authors if a]

            categories = [
                c.get("term", "")
                for c in entry.findall(f"{{{_ATOM_NS}}}category")
                if c.get("term")
            ]

            pdf_url = ""
            for link in entry.findall(f"{{{_ATOM_NS}}}link"):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break
            if not pdf_url:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

            results.append(ArxivResult(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                published=published,
                categories=categories,
                pdf_url=pdf_url,
            ))

        return results

    def _extract_id(self, entry: ET.Element) -> str | None:
        """Extract the bare arXiv ID (e.g. '2301.04567') from an entry."""
        id_text = entry.findtext(f"{{{_ATOM_NS}}}id") or ""
        m = _ID_RE.search(id_text)
        if m:
            # Strip version suffix: "2301.04567v2" → "2301.04567"
            return re.sub(r"v\d+$", "", m.group(1))
        return None


# ---------------------------------------------------------------------------
# Re-ranking helpers
# ---------------------------------------------------------------------------

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rerank_by_embedding(
    results: list[ArxivResult],
    query_embeddings: list[list[float]],
    embedder,
) -> list[ArxivResult]:
    """Re-rank ArxivResults by cosine similarity to the query paper's chunks.

    Embeds each result's abstract, then scores it as the max cosine similarity
    against all query_embeddings (paper chunks).  Results are sorted descending.

    Args:
        results: List of ArxivResult to re-rank.
        query_embeddings: Embeddings from the source paper's chunks.
        embedder: Embedder instance with an .encode() method.

    Returns:
        New list sorted by similarity_score descending.
    """
    if not results or not query_embeddings:
        return results

    abstracts = [r.abstract or r.title for r in results]
    try:
        result_embeddings = embedder.encode(abstracts)
    except Exception:
        return results

    for result, emb in zip(results, result_embeddings):
        emb_list = list(emb)
        result.similarity_score = max(
            _cosine(emb_list, q) for q in query_embeddings
        )

    return sorted(results, key=lambda r: r.similarity_score, reverse=True)


# ---------------------------------------------------------------------------
# High-level convenience function
# ---------------------------------------------------------------------------

def find_related(
    paper_id: str,
    store,
    strategy: str = "all",
    top_k: int = 10,
    rerank: bool = True,
    embedder=None,
) -> list[ArxivResult]:
    """Find arXiv papers related to a paper already in the graph.

    Strategies:
        "topic"    — search using the paper's topic nodes
        "author"   — search using the paper's author nodes
        "arxiv_id" — fetch by stored arxiv_id then search by category
        "all"      — combine all strategies (deduped by arxiv_id)

    Args:
        paper_id: Graph paper ID.
        store: GraphStore instance.
        strategy: One of "topic", "author", "arxiv_id", "all".
        top_k: Number of results to return.
        rerank: If True and embedder is provided, re-rank by embedding similarity.
        embedder: Embedder instance for re-ranking (optional).

    Returns:
        List of ArxivResult ordered by similarity_score (or arXiv relevance if
        no embedder supplied).
    """
    ctx = store.paper_context(paper_id)
    if not ctx:
        return []

    client = ArxivClient()
    fetch_n = top_k * 3  # fetch more, trim after re-ranking
    seen: dict[str, ArxivResult] = {}

    def _add(results: list[ArxivResult]) -> None:
        for r in results:
            if r.arxiv_id not in seen:
                seen[r.arxiv_id] = r

    if strategy in ("topic", "all") and ctx["topics"]:
        terms = ctx["topics"][:5]  # top 5 topics
        _add(client.search(terms=terms, max_results=fetch_n))

    if strategy in ("author", "all") and ctx["authors"]:
        for author in ctx["authors"][:3]:
            _add(client.search(terms=[author], max_results=fetch_n // 3))

    if strategy in ("arxiv_id", "all") and ctx["arxiv_id"]:
        _add(client.search(arxiv_id=ctx["arxiv_id"], max_results=fetch_n))

    # Fall back to title search if nothing found
    if not seen and ctx["title"]:
        _add(client.search(terms=[ctx["title"]], max_results=fetch_n))

    # Remove the source paper itself
    seen.pop(ctx["arxiv_id"], None)

    candidates = list(seen.values())

    if rerank and embedder and ctx["chunk_embeddings"]:
        candidates = rerank_by_embedding(candidates, ctx["chunk_embeddings"], embedder)

    return candidates[:top_k]
