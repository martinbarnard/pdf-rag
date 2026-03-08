"""RAG retrieval pipeline: embed query → vector search → graph expand → Claude answer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pdf_rag.config import DEFAULT_DB_PATH
from pdf_rag.graph.store import GraphStore
from pdf_rag.ingestion.embedder import Embedder


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
        return RetrievalResult(chunks=[], context="", answer=_call_claude("", query), sources=[])

    # 3. Graph context expansion — find papers and topics for retrieved chunks
    context_parts: list[str] = []
    sources: list[str] = []

    # Get parent papers for each chunk
    chunk_ids = [c["id"] for c in chunks]
    for chunk_id in chunk_ids:
        r = store.execute(
            "MATCH (p:Paper)-[:HAS_CHUNK]->(c:Chunk {id: $cid}) RETURN p.id, p.title, p.year",
            {"cid": chunk_id},
        )
        while r.has_next():
            row = r.get_next()
            paper_ref = f"{row[1]} ({row[2]})" if row[2] else row[1]
            if paper_ref not in sources:
                sources.append(paper_ref)

    # Build context from chunks
    for chunk in chunks:
        context_parts.append(f"[{chunk['section']}] {chunk['text']}")

    context = "\n\n".join(context_parts)

    # 4 + 5. Assemble prompt and call Claude
    answer = _call_claude(context, query)

    return RetrievalResult(chunks=chunks, context=context, answer=answer, sources=sources)


def _call_claude(context: str, query: str) -> str:
    """Call Claude via the Anthropic SDK and return the answer text."""
    import anthropic

    client = anthropic.Anthropic()

    if context:
        system = (
            "You are a research assistant. Answer the user's question using only "
            "the provided context from scientific papers. Cite sources where possible. "
            "If the context does not contain enough information, say so clearly."
        )
        user_message = f"Context:\n{context}\n\nQuestion: {query}"
    else:
        system = "You are a research assistant."
        user_message = f"Question: {query}\n\n(No relevant documents found in the database.)"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text
