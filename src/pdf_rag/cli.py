"""Typer CLI entry point for pdf-rag."""

from __future__ import annotations

import shutil
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
    from pdf_rag.config import DEFAULT_DB_PATH, DEFAULT_INGEST_DIR
    from pdf_rag.extraction.entities import EntityExtractor
    from pdf_rag.ingestion.embedder import Embedder
    from pdf_rag.pipeline import ingest_document

    db_path = db or DEFAULT_DB_PATH
    ingest_dir = DEFAULT_INGEST_DIR
    ingest_dir.mkdir(parents=True, exist_ok=True)

    # Collect files
    if path.is_dir():
        suffixes = {".pdf", ".docx", ".md", ".html", ".htm", ".tex"}
        files = [f for f in path.rglob("*") if f.suffix.lower() in suffixes]
    else:
        files = [path]

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[dim]Documents folder:[/dim] [cyan]{ingest_dir}[/cyan]")

    # Load models once, reuse across files
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        t = progress.add_task("Loading models...", total=None)
        embedder = Embedder()
        extractor = EntityExtractor()
        progress.remove_task(t)

    total = len(files)
    success = 0
    for i, file in enumerate(files, 1):
        # Copy to ingest_dir unless already inside it
        try:
            file.resolve().relative_to(ingest_dir.resolve())
            ingest_path = file  # already inside ingest_dir
        except ValueError:
            dest = ingest_dir / file.name
            if dest.exists() and dest.resolve() != file.resolve():
                # avoid overwriting — suffix with counter
                stem, suffix = file.stem, file.suffix
                counter = 1
                while dest.exists():
                    dest = ingest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            if not dest.exists():
                shutil.copy2(file, dest)
                console.print(f"  [dim]→ copied to {dest}[/dim]")
            ingest_path = dest

        console.print(f"[dim]({i}/{total})[/dim] Ingesting [bold]{file.name}[/bold]...")
        try:
            result = ingest_document(ingest_path, db_path=db_path, embedder=embedder, extractor=extractor)
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
    top_k: int = typer.Option(5, "--top-k", help="Number of chunks to retrieve."),
) -> None:
    """Search the graph database and answer using retrieved context."""
    from pdf_rag.config import DEFAULT_DB_PATH
    from pdf_rag.retriever import retrieve

    db_path = db or DEFAULT_DB_PATH
    if not Path(db_path).exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        t = progress.add_task("Searching...", total=None)
        result = retrieve(query, db_path=db_path, top_k=top_k)
        progress.remove_task(t)

    if result.chunks:
        console.print("\n[bold cyan]Retrieved chunks:[/bold cyan]")
        for i, chunk in enumerate(result.chunks, 1):
            console.print(
                f"  [dim]{i}.[/dim] [{chunk['section']}] "
                f"[dim](score: {chunk['score']:.3f})[/dim]\n"
                f"     {chunk['text'][:120]}..."
            )

    if result.sources:
        console.print("\n[bold]Sources:[/bold] " + " · ".join(result.sources))

    console.print(f"\n[bold green]Answer:[/bold green]\n{result.answer}")


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


@app.command()
def models() -> None:
    """List LLM models available on the local server and show active backend config."""
    from pdf_rag.llm import LLM_BACKEND, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL, list_local_models, probe_local

    console.print(f"[bold]Backend:[/bold] [cyan]{LLM_BACKEND}[/cyan]")
    console.print(f"[bold]Local server:[/bold] {LOCAL_LLM_BASE_URL}")
    console.print(f"[bold]Configured model:[/bold] {LOCAL_LLM_MODEL}\n")

    reachable = probe_local()
    if not reachable:
        console.print("[yellow]Local server not reachable.[/yellow]")
        return

    available = list_local_models()
    if not available:
        console.print("[yellow]No models returned by server.[/yellow]")
        return

    table = Table(title=f"Models at {LOCAL_LLM_BASE_URL}")
    table.add_column("Model ID", style="cyan")
    table.add_column("Active", justify="center")
    for model_id in available:
        active = "[green]✓[/green]" if model_id == LOCAL_LLM_MODEL else ""
        table.add_row(model_id, active)
    console.print(table)


if __name__ == "__main__":
    app()
