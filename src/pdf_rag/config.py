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
