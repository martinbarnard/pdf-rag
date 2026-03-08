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


_TITLE_PROMPT = "Write a title (10 words or fewer) for this text:\n\n{excerpt}"


def _extract_title(raw: str, fallback: str) -> str:
    """Return the first non-empty line from the model response, stripped of decoration."""
    cleaned = _strip_thinking(raw)
    for line in cleaned.splitlines():
        line = line.strip().strip("*").strip("-").strip('"').strip("'").strip()
        if line:
            return line
    return fallback


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
            raw = _call_local_raw(prompt)
        else:  # auto
            if probe_local():
                try:
                    raw = _call_local_raw(prompt)
                except Exception:
                    raw = _call_anthropic_raw(prompt)
            else:
                raw = _call_anthropic_raw(prompt)
        return _extract_title(raw, fallback)
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


def _call_local_raw(prompt: str) -> str:
    """Call local OpenAI-compatible server with a single user prompt.

    Uses an empty assistant prefill so Qwen3 and similar thinking models skip
    the reasoning narration and complete directly into the answer.
    """
    import httpx

    url = LOCAL_LLM_BASE_URL.rstrip("/") + "/v1/chat/completions"
    resp = httpx.post(
        url,
        json={
            "model": LOCAL_LLM_MODEL,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": ""},  # prefill — skip preamble
            ],
            "max_tokens": 64,
            "temperature": 0.2,
            # LM Studio / llama.cpp Qwen3 extension — disable thinking mode
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    content: str = resp.json()["choices"][0]["message"]["content"]
    return _strip_thinking(content)


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks produced by Qwen3/DeepSeek-R1."""
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------
# Paper enrichment — summary + keywords via JSON mode
# ---------------------------------------------------------------------------

_ENRICH_PROMPT = """\
You are a scientific paper analyst. Given the text below, respond with ONLY valid JSON \
and nothing else — no explanation, no markdown fences.

The JSON must have exactly this shape:
{{"summary": "<2-3 sentence summary of the paper's contribution>", "keywords": ["keyword1", "keyword2", ...]}}

Rules:
- summary: 2-3 sentences, plain text, describe the main contribution and findings
- keywords: 5-10 short noun phrases (2-4 words each), most important concepts/methods
- Output ONLY the JSON object, starting with {{ and ending with }}

Text:
{text}"""


def enrich_paper(
    text: str,
    backend: str | None = None,
) -> dict[str, str | list[str]]:
    """Generate a summary and keyword list for a paper using the LLM.

    Uses JSON mode to avoid reasoning narration from thinking models.
    Returns a dict with keys ``summary`` (str) and ``keywords`` (list[str]).
    Returns empty values if the LLM is unavailable or parsing fails.

    Compatible with any OpenAI-compatible server (LM Studio, Ollama) and
    Anthropic Claude.  Recommended local models (in preference order):
      - qwen/qwen3.5-9b         — strong; use JSON mode to suppress thinking
      - qwen2.5-7b-instruct     — fast, non-thinking, reliable JSON output
      - mistral-7b-instruct     — good structured output, widely available
      - phi-3-mini-instruct     — lightweight fallback

    Args:
        text: Abstract + first section text (600-1200 chars recommended).
        backend: Override LLM backend ("anthropic", "local", "auto").

    Returns:
        {"summary": str, "keywords": list[str]}
    """
    import json

    empty: dict[str, str | list[str]] = {"summary": "", "keywords": []}
    if not text or not text.strip():
        return empty

    prompt = _ENRICH_PROMPT.format(text=text[:1200])
    resolved = backend if backend is not None else LLM_BACKEND

    try:
        if resolved == "anthropic":
            raw = _call_anthropic_raw(prompt)
        elif resolved == "local":
            raw = _call_local_json(prompt)
        else:  # auto
            if probe_local():
                try:
                    raw = _call_local_json(prompt)
                except Exception:
                    raw = _call_anthropic_raw(prompt)
            else:
                raw = _call_anthropic_raw(prompt)
    except Exception:
        return empty

    # Strip thinking blocks then extract the JSON object
    raw = _strip_thinking(raw)
    # Find the outermost { ... } in case the model added extra prose
    import re
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return empty
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return empty

    summary = str(data.get("summary", "")).strip()
    keywords = [str(k).strip() for k in data.get("keywords", []) if str(k).strip()]
    return {"summary": summary, "keywords": keywords}


def _call_local_json(prompt: str) -> str:
    """Call local server requesting JSON output.

    Passes response_format=json_object when supported (LM Studio ≥0.3,
    Ollama ≥0.1.28), which forces the model to emit valid JSON regardless
    of thinking mode.  Falls back gracefully if the server ignores it.
    """
    import httpx

    url = LOCAL_LLM_BASE_URL.rstrip("/") + "/v1/chat/completions"
    resp = httpx.post(
        url,
        json={
            "model": LOCAL_LLM_MODEL,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "{"},  # prefill opening brace
            ],
            "max_tokens": 512,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    content: str = resp.json()["choices"][0]["message"]["content"]
    # Prepend the prefill brace if the model didn't echo it
    if not content.lstrip().startswith("{"):
        content = "{" + content
    return _strip_thinking(content)


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
