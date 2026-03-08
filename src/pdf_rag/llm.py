"""LLM backend abstraction.

Supports two backends:
  - "anthropic": Anthropic Claude via the official SDK (default)
  - "local": Any OpenAI-compatible server (LM Studio, Ollama, etc.)

Backend is selected by the `backend` argument to `call_llm`, which defaults
to the `LLM_BACKEND` config constant (overridable via the LLM_BACKEND env var).
"""

from __future__ import annotations

import os

from pdf_rag.config import (
    LOCAL_LLM_BASE_URL as _CFG_BASE_URL,
    LOCAL_LLM_MODEL as _CFG_MODEL,
    LLM_BACKEND as _CFG_BACKEND,
)

# Allow env-var overrides at import time
LLM_BACKEND: str = os.environ.get("LLM_BACKEND", _CFG_BACKEND)
LOCAL_LLM_BASE_URL: str = os.environ.get("LOCAL_LLM_BASE_URL", _CFG_BASE_URL)
LOCAL_LLM_MODEL: str = os.environ.get("LOCAL_LLM_MODEL", _CFG_MODEL)

_SYSTEM_WITH_CONTEXT = (
    "You are a research assistant. Answer the user's question using only "
    "the provided context from scientific papers. Cite sources where possible. "
    "If the context does not contain enough information, say so clearly."
)
_SYSTEM_NO_CONTEXT = "You are a research assistant."


def call_llm(context: str, query: str, backend: str | None = None) -> str:
    """Generate an answer using the configured LLM backend.

    Args:
        context: Retrieved text context to ground the answer.
        query: The user's natural language question.
        backend: "anthropic" or "local". Defaults to LLM_BACKEND config/env.

    Returns:
        Answer string from the LLM.

    Raises:
        ValueError: If backend is not "anthropic" or "local".
    """
    resolved = backend if backend is not None else LLM_BACKEND
    if resolved == "anthropic":
        return _call_anthropic(context, query)
    if resolved == "local":
        return _call_local(context, query)
    raise ValueError(f"Unknown LLM backend: {resolved!r}. Choose 'anthropic' or 'local'.")


def _call_anthropic(context: str, query: str) -> str:
    """Call Anthropic Claude and return the answer text."""
    import anthropic

    client = anthropic.Anthropic()
    system = _SYSTEM_WITH_CONTEXT if context else _SYSTEM_NO_CONTEXT
    user_message = (
        f"Context:\n{context}\n\nQuestion: {query}"
        if context
        else f"Question: {query}\n\n(No relevant documents found in the database.)"
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _call_local(context: str, query: str) -> str:
    """Call a local OpenAI-compatible server (LM Studio / Ollama) and return the answer."""
    import httpx

    system = _SYSTEM_WITH_CONTEXT if context else _SYSTEM_NO_CONTEXT
    user_message = (
        f"Context:\n{context}\n\nQuestion: {query}"
        if context
        else f"Question: {query}\n\n(No relevant documents found in the database.)"
    )
    url = LOCAL_LLM_BASE_URL.rstrip("/") + "/v1/chat/completions"
    resp = httpx.post(
        url,
        json={
            "model": LOCAL_LLM_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
