"""Typer CLI entry point for pdf-rag."""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="pdf-rag",
    help="Graph-RAG CLI for scientific PDF ingestion and search.",
    add_completion=False,
)
console = Console()


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Path to a document file or directory."),
    db: Path = typer.Option(None, "--db", help="Path to the kuzu database directory."),
) -> None:
    """Ingest one or more documents into the graph database."""
    from pdf_rag.config import DEFAULT_DB_PATH
    from pdf_rag.extraction.entities import EntityExtractor
    from pdf_rag.ingestion.embedder import Embedder
    from pdf_rag.pipeline import ingest_document

    db_path = db or DEFAULT_DB_PATH

    # Collect files
    if path.is_dir():
        suffixes = {".pdf", ".docx", ".md", ".html", ".htm", ".tex"}
        files = [f for f in path.rglob("*") if f.suffix.lower() in suffixes]
    else:
        files = [path]

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        raise typer.Exit(1)

    # Load models once, reuse across files
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        t = progress.add_task("Loading models...", total=None)
        embedder = Embedder()
        extractor = EntityExtractor()
        progress.remove_task(t)

    total = len(files)
    success = 0
    for i, file in enumerate(files, 1):
        console.print(f"[dim]({i}/{total})[/dim] Ingesting [bold]{file.name}[/bold]...")
        try:
            result = ingest_document(file, db_path=db_path, embedder=embedder, extractor=extractor)
            console.print(
                f"  [green]✓[/green] {result.chunk_count} chunks, "
                f"{result.entity_count} entities, "
                f"{result.citation_count} citations"
            )
            success += 1
        except (FileNotFoundError, ValueError) as e:
            console.print(f"  [red]✗[/red] {e}")

    console.print(f"\n[bold]Done:[/bold] {success}/{total} files ingested into [cyan]{db_path}[/cyan]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language search query."),
    db: Path = typer.Option(None, "--db", help="Path to the kuzu database directory."),
    top_k: int = typer.Option(5, "--top-k", help="Number of results to return."),
) -> None:
    """Search the graph database with a natural-language query."""
    raise NotImplementedError("search is not yet implemented")


@app.command()
def stats(
    db: Path = typer.Option(None, "--db", help="Path to the kuzu database directory."),
) -> None:
    """Display statistics about the graph database."""
    from pdf_rag.config import DEFAULT_DB_PATH
    from pdf_rag.graph.store import GraphStore

    db_path = db or DEFAULT_DB_PATH
    if not Path(db_path).exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(1)

    store = GraphStore(db_path)
    table = Table(title="Graph Database Statistics")
    table.add_column("Node Type", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for label in ("Paper", "Author", "Topic", "Chunk", "Institution", "Venue"):
        r = store.execute(f"MATCH (n:{label}) RETURN count(n)")
        count = r.get_next()[0]
        table.add_row(label, str(count))

    console.print(table)


if __name__ == "__main__":
    app()
