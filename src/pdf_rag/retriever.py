"""RAG retrieval pipeline: embed query → vector search → graph expand → LLM answer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pdf_rag.config import DEFAULT_DB_PATH
from pdf_rag.graph.store import GraphStore
from pdf_rag.ingestion.embedder import Embedder
from pdf_rag.llm import call_llm


@dataclass
class RetrievalResult:
    chunks: list[dict]
    context: str
    answer: str
    sources: list[str] = field(default_factory=list)


def retrieve(
    query: str,
    db_path: Path | None = None,
    top_k: int = 5,
    embedder: Embedder | None = None,
) -> RetrievalResult:
    """Run the full RAG pipeline for a query.

    Steps:
      1. Embed the query
      2. Vector search top-k chunks
      3. Expand graph context (related topics, paper authors)
      4. Assemble prompt
      5. Call Claude for an answer

    Args:
        query: Natural language question.
        db_path: Path to the kuzu database.
        top_k: Number of chunks to retrieve.
        embedder: Optional pre-loaded Embedder.

    Returns:
        RetrievalResult with chunks, assembled context, and Claude's answer.
    """
    db_path = db_path or DEFAULT_DB_PATH
    embedder = embedder or Embedder()
    store = GraphStore(db_path)

    # 1. Embed query
    query_embedding = embedder.encode([query])[0]

    # 2. Vector search
    chunks = store.search_similar_chunks(query_embedding, top_k=top_k)

    if not chunks:
        return RetrievalResult(chunks=[], context="", answer=call_llm("", query), sources=[])

    # 3. Graph context expansion
    context_parts: list[str] = []
    sources: list[str] = []
    paper_ids: list[str] = []

    # 3a. Get parent papers for each chunk
    for chunk in chunks:
        r = store.execute(
            "MATCH (p:Paper)-[:HAS_CHUNK]->(c:Chunk {id: $cid}) RETURN p.id, p.title, p.year",
            {"cid": chunk["id"]},
        )
        while r.has_next():
            row = r.get_next()
            pid, title, year = row[0], row[1], row[2]
            paper_ref = f"{title} ({year})" if year else title
            if paper_ref not in sources:
                sources.append(paper_ref)
            if pid not in paper_ids:
                paper_ids.append(pid)

    # 3b. Expand: authors and topics for retrieved papers
    graph_context_parts: list[str] = []
    for pid in paper_ids:
        ar = store.execute(
            "MATCH (a:Author)-[:AUTHORED]->(p:Paper {id: $pid}) RETURN a.canonical_name",
            {"pid": pid},
        )
        author_names = []
        while ar.has_next():
            author_names.append(ar.get_next()[0])

        tr = store.execute(
            "MATCH (p:Paper {id: $pid})-[:DISCUSSES]->(t:Topic) RETURN t.canonical_name",
            {"pid": pid},
        )
        topic_names = []
        while tr.has_next():
            topic_names.append(tr.get_next()[0])

        if author_names or topic_names:
            parts = []
            if author_names:
                parts.append(f"Authors: {', '.join(author_names)}")
            if topic_names:
                parts.append(f"Topics: {', '.join(topic_names)}")
            graph_context_parts.append(" | ".join(parts))

    # 3c. Related topics for chunk-mentioned topics
    for chunk in chunks:
        tr = store.execute(
            "MATCH (c:Chunk {id: $cid})-[:MENTIONS_TOPIC]->(t:Topic)-[:RELATED_TO]->(r:Topic) "
            "RETURN r.canonical_name LIMIT 3",
            {"cid": chunk["id"]},
        )
        related = []
        while tr.has_next():
            related.append(tr.get_next()[0])
        if related:
            graph_context_parts.append(f"Related topics: {', '.join(related)}")

    # Build final context: chunks first, then graph metadata
    for chunk in chunks:
        context_parts.append(f"[{chunk['section']}] {chunk['text']}")
    if graph_context_parts:
        context_parts.append("Graph context: " + " | ".join(graph_context_parts))

    context = "\n\n".join(context_parts)

    # 4 + 5. Assemble prompt and call LLM
    answer = call_llm(context, query)

    return RetrievalResult(chunks=chunks, context=context, answer=answer, sources=sources)
