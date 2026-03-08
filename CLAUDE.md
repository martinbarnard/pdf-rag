# PDF RAG Project — Claude Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

We also use jcodemunch to keep our token costs down!

## Project Overview

A personal PDF Retrieval-Augmented Generation (RAG) system built in Python.

## Language & Stack

- **Language**: Python 3.11+
- **Prefer open-source tooling** over proprietary/paid services where feasible
- Use the Anthropic SDK (`anthropic`) for LLM calls

## Workflow

- **TDD**: Write tests before implementation. Red → Green → Refactor.
- Use `pytest` as the test runner
- Tests live in `tests/` mirroring the `src/` structure
- Run tests after every meaningful change

## Code Style

- Follow PEP 8
- Use type hints throughout
- Keep functions small and focused
- No unnecessary abstractions — solve the current problem, not hypothetical future ones

## Tooling Preferences

- **Embeddings**: open-source models (e.g. `sentence-transformers`)
- **Vector store**: open-source (e.g. `chromadb`, `qdrant`, or `faiss`)
- **PDF parsing**: open-source (e.g. `pymupdf`, `pdfplumber`)
- **LLM**: Anthropic Claude via `anthropic` SDK
- **Dependency management**: `uv` (preferred) or `pip` with `pyproject.toml`

## Memory & Context

- Save architectural decisions and patterns to `/home/martinb/.claude/projects/-mnt-sdb-src-ML-personal-pdf-rag/memory/`
- Keep `MEMORY.md` concise (under 200 lines); use topic files for details

## Commit Style

- Conventional commits: `feat:`, `fix:`, `test:`, `refactor:`, `chore:`
- Only commit when explicitly asked
