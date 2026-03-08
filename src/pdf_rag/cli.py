"""Typer CLI entry point for pdf-rag."""

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="pdf-rag",
    help="Graph-RAG CLI for scientific PDF ingestion and search.",
    add_completion=False,
)
console = Console()


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Path to a PDF file or directory of PDFs."),
    db: Path = typer.Option(None, "--db", help="Path to the kuzu database directory."),
) -> None:
    """Ingest one or more PDF files into the graph database."""
    raise NotImplementedError("ingest is not yet implemented")


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language search query."),
    db: Path = typer.Option(None, "--db", help="Path to the kuzu database directory."),
    top_k: int = typer.Option(10, "--top-k", help="Number of results to return."),
) -> None:
    """Search the graph database with a natural-language query."""
    raise NotImplementedError("search is not yet implemented")


@app.command()
def stats(
    db: Path = typer.Option(None, "--db", help="Path to the kuzu database directory."),
) -> None:
    """Display statistics about the graph database."""
    raise NotImplementedError("stats is not yet implemented")


if __name__ == "__main__":
    app()
