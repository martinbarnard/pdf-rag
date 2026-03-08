"""Project-wide configuration constants."""

from pathlib import Path

# Storage
DEFAULT_DB_PATH: Path = Path("~/.pdf_rag/graph.db").expanduser()

# Embedding model — placeholder: verify exact HF model name before use.
# Qwen3-Embedding-0.6B may not yet be published; update to the confirmed
# model ID once available (e.g. "Qwen/Qwen3-Embedding-0.6B").
DEFAULT_EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"

# GLiNER2-compatible entity extraction model
DEFAULT_GLINER_MODEL: str = "knowledgator/gliner-multitask-large-v0.5"

# Entity deduplication — cosine similarity threshold
SIMILARITY_THRESHOLD: float = 0.85

# Chunking
CHUNK_SIZE: int = 512
CHUNK_OVERLAP: int = 64

# Embedding dimension — must match the chosen model output size.
# all-MiniLM-L6-v2: 384, Qwen3-Embedding-0.6B: 1024
EMBEDDING_DIM: int = 1024

# Embedding backend:
#   "auto"      — use LM Studio /v1/embeddings if reachable, else sentence-transformers
#   "local"     — always use LM Studio /v1/embeddings
#   "local_st"  — always use sentence-transformers in-process
EMBEDDING_BACKEND: str = "auto"
LOCAL_EMBEDDING_BASE_URL: str = "http://localhost:1234"          # LM Studio default
LOCAL_EMBEDDING_MODEL: str = "text-embedding-qwen3-embedding-0.6b"  # model ID as shown in LM Studio

# LLM backend selection:
#   "anthropic" — always use Anthropic Claude (requires ANTHROPIC_API_KEY)
#   "local"     — always use local OpenAI-compatible server (LM Studio / Ollama)
#   "auto"      — probe local server first; fall back to Anthropic if unreachable
LLM_BACKEND: str = "auto"
LOCAL_LLM_BASE_URL: str = "http://localhost:1234"    # LM Studio default port
LOCAL_LLM_MODEL: str = "qwen/qwen3.5-9b"             # model tag as loaded in LM Studio
LOCAL_LLM_PROBE_TIMEOUT: float = 3.0                 # seconds to wait when probing local server

# Device placement for ML models.
# EMBEDDING_DEVICE is only used when EMBEDDING_BACKEND="local_st" (sentence-transformers
# in-process). When EMBEDDING_BACKEND="auto" or "local", embeddings are offloaded to
# LM Studio and no GPU memory is used by the embedder.
EMBEDDING_DEVICE: str = "cpu"   # fallback device for in-process sentence-transformers
GLINER_DEVICE: str = "cpu"      # always CPU to avoid OOM during ingest

# Docling layout/table model device. Docling defaults to "auto" (CUDA if available),
# which OOMs when LM Studio is also running. Set to "cpu" to be safe.
DOCLING_DEVICE: str = "cpu"
