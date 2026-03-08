"""Search and RAG query API endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/search")
async def search(body: SearchRequest, request: Request) -> dict:
    """Run vector search + RAG pipeline and return results synchronously."""
    from pdf_rag.retriever import retrieve

    result = retrieve(body.query, db_path=request.app.state.db_path, top_k=body.top_k)
    return {
        "chunks": result.chunks,
        "answer": result.answer,
        "sources": result.sources,
        "context": result.context,
    }


@router.get("/ask")
async def ask(
    query: str = Query(..., description="Natural language question"),
    top_k: int = Query(5, description="Number of chunks to retrieve"),
    request: Request = None,
) -> StreamingResponse:
    """Stream a RAG answer as Server-Sent Events.

    Each SSE event carries a JSON payload:
      - type=chunk: a retrieved text chunk
      - type=answer_token: a token of Claude's answer
      - type=done: final event with sources list
    """
    async def event_stream():
        from pdf_rag.retriever import retrieve

        result = retrieve(query, db_path=request.app.state.db_path, top_k=top_k)

        # Emit retrieved chunks
        for chunk in result.chunks:
            payload = json.dumps({"type": "chunk", "data": chunk})
            yield f"data: {payload}\n\n"

        # Emit answer tokens (word-by-word simulation for now;
        # replace with real streaming when anthropic streaming is wired)
        for word in result.answer.split():
            payload = json.dumps({"type": "answer_token", "data": word + " "})
            yield f"data: {payload}\n\n"

        # Emit done event
        payload = json.dumps({"type": "done", "sources": result.sources})
        yield f"data: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
