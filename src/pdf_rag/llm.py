"""LLM backend abstraction.

Supports three backends:
  - "anthropic": Anthropic Claude via the official SDK (requires ANTHROPIC_API_KEY)
  - "local": Any OpenAI-compatible server (LM Studio, Ollama, etc.)
  - "auto": Probe local server first; fall back to Anthropic if unreachable or failing

Backend is selected by the `backend` argument to `call_llm`, which defaults
to the `LLM_BACKEND` config constant (overridable via the LLM_BACKEND env var).

Model discovery:
  - list_local_models() — returns model IDs available on the local server
  - probe_local()       — returns True if the local server is reachable
"""

from __future__ import annotations

import os

from pdf_rag.config import (
    LOCAL_LLM_BASE_URL as _CFG_BASE_URL,
    LOCAL_LLM_MODEL as _CFG_MODEL,
    LOCAL_LLM_PROBE_TIMEOUT as _CFG_PROBE_TIMEOUT,
    LLM_BACKEND as _CFG_BACKEND,
)

# Allow env-var overrides at import time
LLM_BACKEND: str = os.environ.get("LLM_BACKEND", _CFG_BACKEND)
LOCAL_LLM_BASE_URL: str = os.environ.get("LOCAL_LLM_BASE_URL", _CFG_BASE_URL)
LOCAL_LLM_MODEL: str = os.environ.get("LOCAL_LLM_MODEL", _CFG_MODEL)
LOCAL_LLM_PROBE_TIMEOUT: float = float(
    os.environ.get("LOCAL_LLM_PROBE_TIMEOUT", _CFG_PROBE_TIMEOUT)
)

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
        backend: "anthropic", "local", or "auto". Defaults to LLM_BACKEND config/env.
                 "auto" probes the local server first and falls back to Anthropic.

    Returns:
        Answer string from the LLM.

    Raises:
        ValueError: If backend is not "anthropic", "local", or "auto".
    """
    resolved = backend if backend is not None else LLM_BACKEND
    if resolved == "anthropic":
        return _call_anthropic(context, query)
    if resolved == "local":
        return _call_local(context, query)
    if resolved == "auto":
        return _call_auto(context, query)
    raise ValueError(
        f"Unknown LLM backend: {resolved!r}. Choose 'anthropic', 'local', or 'auto'."
    )


def probe_local() -> bool:
    """Return True if the local LLM server is reachable and responding.

    Hits GET /v1/models with a short timeout. Any exception returns False.
    """
    import httpx

    url = LOCAL_LLM_BASE_URL.rstrip("/") + "/v1/models"
    try:
        resp = httpx.get(url, timeout=LOCAL_LLM_PROBE_TIMEOUT)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def list_local_models() -> list[str]:
    """Return model IDs available on the local OpenAI-compatible server.

    Returns an empty list if the server is unreachable or returns no models.
    """
    import httpx

    url = LOCAL_LLM_BASE_URL.rstrip("/") + "/v1/models"
    try:
        resp = httpx.get(url, timeout=LOCAL_LLM_PROBE_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [m["id"] for m in data if "id" in m]
    except Exception:
        return []


def _call_auto(context: str, query: str) -> str:
    """Try local server first; fall back to Anthropic on any failure."""
    if probe_local():
        try:
            return _call_local(context, query)
        except Exception:
            pass
    return _call_anthropic(context, query)


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


_TITLE_SYSTEM = (
    "You output only the requested text — nothing else. "
    "No preamble, no explanation, no punctuation around the answer."
)

_TITLE_PROMPT = (
    "Write a concise title (10 words or fewer) for this academic excerpt. "
    "Output the title only.\n\nExcerpt:\n{excerpt}"
)


def generate_title(text: str, backend: str | None = None, fallback: str = "Untitled") -> str:
    """Generate a short semantic title from document text using the LLM.

    Args:
        text: Abstract or first section text to summarise.
        backend: LLM backend override ("anthropic", "local", "auto").
        fallback: Value to return if text is empty or the LLM call fails.

    Returns:
        A short title string (stripped of surrounding quotes/whitespace).
    """
    if not text or not text.strip():
        return fallback

    prompt = _TITLE_PROMPT.format(excerpt=text[:600])
    resolved = backend if backend is not None else LLM_BACKEND
    try:
        if resolved == "anthropic":
            raw = _call_anthropic_raw(prompt)
        elif resolved == "local":
            raw = _call_local_raw(prompt, system=_TITLE_SYSTEM)
        else:  # auto
            if probe_local():
                try:
                    raw = _call_local_raw(prompt, system=_TITLE_SYSTEM)
                except Exception:
                    raw = _call_anthropic_raw(prompt)
            else:
                raw = _call_anthropic_raw(prompt)
        # Some models narrate before answering — take the last non-empty line
        lines = [l.strip().strip('"').strip("'") for l in raw.splitlines() if l.strip()]
        return lines[-1] if lines else fallback
    except Exception:
        return fallback


def _call_anthropic_raw(prompt: str) -> str:
    """Call Anthropic Claude with a single user prompt (no system message)."""
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_local_raw(prompt: str, system: str | None = None) -> str:
    """Call local OpenAI-compatible server with a single user prompt."""
    import httpx

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    url = LOCAL_LLM_BASE_URL.rstrip("/") + "/v1/chat/completions"
    resp = httpx.post(
        url,
        json={
            "model": LOCAL_LLM_MODEL,
            "messages": messages,
            "max_tokens": 64,
            "temperature": 0.2,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    content: str = resp.json()["choices"][0]["message"]["content"]
    return _strip_thinking(content)


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks produced by Qwen3/DeepSeek-R1.

    Also strips any leading prose that precedes the actual answer — some models
    narrate their reasoning in plain text before giving the result. We take the
    last non-empty line as the answer when the text contains multiple lines.
    """
    import re
    # Remove tagged thinking blocks
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned


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
    content: str = resp.json()["choices"][0]["message"]["content"]
    return _strip_thinking(content)
