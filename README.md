# pdf-rag

A local-first Graph-RAG system for scientific papers. Ingests PDF, DOCX, Markdown, HTML, and LaTeX documents, builds a knowledge graph of papers, authors, topics, and citations, and answers questions using retrieved context.

## Stack

| Layer | Technology |
|---|---|
| Parsing | [docling](https://github.com/DS4SD/docling) |
| Embeddings | `Qwen/Qwen3-Embedding-0.6B` via [LM Studio](https://lmstudio.ai) or sentence-transformers |
| Graph + vector DB | [kuzu](https://kuzudb.com) (embedded, Cypher, built-in vector search) |
| Entity extraction | [GLiNER2](https://github.com/urchade/GLiNER) (`knowledgator/gliner-multitask-large-v0.5`) |
| LLM | Local via LM Studio / Ollama **or** Anthropic Claude (auto-detected) |
| CLI | [Typer](https://typer.tiangolo.com) + [Rich](https://rich.readthedocs.io) |
| Server | [FastAPI](https://fastapi.tiangolo.com) + uvicorn |
| Frontend | React + Vite + Tailwind CSS + Cytoscape.js |

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 22+ (for building the frontend — pre-built assets are included)
- **Recommended**: [LM Studio](https://lmstudio.ai) with the following models loaded:
  - Chat: `Qwen/Qwen2.5-7B-Instruct` or `Qwen/Qwen3.5-9B` (Q4_K_M)
  - Embeddings: `Qwen/Qwen3-Embedding-0.6B`
- **Optional**: `ANTHROPIC_API_KEY` env var if you want Claude as fallback

---

## Installation

```bash
git clone https://github.com/martinbarnard/pdf-rag.git
cd pdf-rag
uv sync
```

This installs all Python dependencies into a local `.venv`.

---

## Configuration

Key settings in `src/pdf_rag/config.py` (all overridable via environment variables):

| Variable | Default | Description |
|---|---|---|
| `LLM_BACKEND` | `auto` | `auto` / `local` / `anthropic` |
| `LOCAL_LLM_BASE_URL` | `http://localhost:1234` | LM Studio / Ollama base URL |
| `LOCAL_LLM_MODEL` | `qwen/qwen3.5-9b` | Chat model name as shown in LM Studio |
| `EMBEDDING_BACKEND` | `auto` | `auto` / `local` / `local_st` |
| `LOCAL_EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | Embedding model name in LM Studio |
| `DEFAULT_DB_PATH` | `~/.pdf_rag/graph.db` | kuzu database location |
| `GLINER_DEVICE` | `cpu` | Device for entity extraction |

`auto` mode probes `http://localhost:1234/v1/models` — if LM Studio is running it is used automatically; otherwise falls back to Anthropic (LLM) or sentence-transformers (embeddings).

---

## LM Studio setup

1. Open LM Studio → **My Models**
2. Download and load:
   - A chat model: `Qwen/Qwen2.5-7B-Instruct` (Q4_K_M, ~4.5 GB) — fits on 12 GB VRAM alongside the embedding model
   - An embedding model: `Qwen/Qwen3-Embedding-0.6B` (~600 MB)
3. Start the **Local Server** on port `1234` (default)
4. Verify: `curl http://localhost:1234/v1/models`

---

## CLI usage

### Ingest documents

```bash
# Single file
uv run pdf-rag ingest path/to/paper.pdf

# Entire directory (recursive)
uv run pdf-rag ingest path/to/papers/

# Custom database location
uv run pdf-rag ingest paper.pdf --db ~/.pdf_rag/myproject.db
```

### Search / ask questions

```bash
uv run pdf-rag search "What methods are used for transformer pre-training?"
uv run pdf-rag search "Who are the authors of the attention paper?" --top-k 10
```

### Explore database stats

```bash
uv run pdf-rag stats
```

### List available LLM models

```bash
uv run pdf-rag models
```

---

## Web interface

Start the server:

```bash
uv run pdf-rag-serve
# or with options:
uv run pdf-rag-serve --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/app** in your browser.

### Pages

| Page | Description |
|---|---|
| **Graph** | Interactive Cytoscape.js network of papers, authors, and topics. Click a node to see details and expand neighbours. Force / tree / circle layouts. |
| **Papers** | Searchable list of ingested papers with full detail panel (abstract, authors, topics, citation counts). |
| **Topics** | Topic-only graph view. Click a topic to see related topics and similarity weights. |
| **Search** | Streaming RAG search — type a question, get retrieved chunks and a streamed LLM answer. |
| **Ingest** | Drag-and-drop file upload to ingest documents directly from the browser. |

### API

The FastAPI server exposes a REST API at `/api/`. Interactive docs at **http://localhost:8000/docs**.

Key endpoints:

```
GET  /api/graph/overview          Full graph snapshot (Cytoscape.js format)
GET  /api/papers/{id}             Paper detail with authors, topics, citation counts
GET  /api/papers/{id}/citing      Papers that cite this paper
GET  /api/papers/{id}/cited       Papers cited by this paper
GET  /api/authors/{id}/papers     Papers by an author
GET  /api/authors/{id}/coauthors  Co-author network
GET  /api/topics/{id}/papers      Papers on a topic
GET  /api/topics/{id}/related     Related topics with similarity weights
GET  /api/stats                   Node counts by type
GET  /api/models                  Available LLM models + backend status
POST /api/ingest                  Upload and ingest a file (multipart/form-data)
POST /api/search                  Synchronous RAG query
GET  /api/ask                     Streaming RAG query (Server-Sent Events)
```

---

## Development

### Run tests

```bash
uv run pytest
uv run pytest --cov=pdf_rag --cov-report=term-missing
```

### Rebuild the frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server with HMR (proxies /api to localhost:8000)
npm run build    # Production build → src/pdf_rag/server/static/
```

### Project structure

```
src/pdf_rag/
├── config.py              Central configuration constants
├── cli.py                 Typer CLI entry point
├── pipeline.py            Ingestion orchestrator
├── retriever.py           RAG retrieval pipeline
├── llm.py                 LLM backend abstraction (local / Anthropic / auto)
├── ingestion/
│   ├── parser.py          docling document parser
│   ├── chunker.py         Section-aware chunker
│   └── embedder.py        Embedding (LM Studio HTTP or sentence-transformers)
├── extraction/
│   ├── entities.py        GLiNER2 entity extractor
│   ├── normaliser.py      Author/topic deduplication (rapidfuzz)
│   └── citations.py       DOI/arXiv citation extractor
├── graph/
│   ├── schema.py          kuzu DDL
│   └── store.py           GraphStore CRUD + traversal
└── server/
    ├── main.py            FastAPI app factory
    └── routers/
        ├── graph.py       Graph traversal endpoints
        ├── search.py      RAG + streaming endpoints
        └── ingest.py      File upload endpoint
frontend/                  React + Vite source
```

---

## Acknowledgements

Uses the [arXiv](https://arxiv.org) API for related paper search (planned). Thank you to arXiv for use of its open access interoperability.

Graph database powered by [kuzu](https://kuzudb.com). Entity extraction by [GLiNER](https://github.com/urchade/GLiNER).
