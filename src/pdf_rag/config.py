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

# Device placement for ML models.
# GLiNER defaults to CPU to avoid competing with the embedding model for VRAM.
# Set EMBEDDING_DEVICE="cpu" if GPU memory is too constrained for the embedding model.
EMBEDDING_DEVICE: str = "cuda"   # "cuda" or "cpu"
GLINER_DEVICE: str = "cpu"       # "cuda" or "cpu"
