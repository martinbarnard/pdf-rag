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
    batch_size: int = typer.Option(0, "--batch-size", help="Max files per batch (0 = no limit)."),
    batch_mb: float = typer.Option(50.0, "--batch-mb", help="Max total MB per batch (0 = no limit)."),
) -> None:
    """Ingest one or more documents into the graph database.

    Large collections are processed in batches to bound peak memory usage.
    Between batches, parsed document objects are released and garbage-collected.
    Models (embedder, entity extractor) are loaded once and reused across all batches.
    """
    import gc

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

    # Load models once, reuse across all batches
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        t = progress.add_task("Loading models...", total=None)
        embedder = Embedder()
        extractor = EntityExtractor()
        progress.remove_task(t)

    # Build batches respecting --batch-size and --batch-mb limits
    batches: list[list[Path]] = []
    current_batch: list[Path] = []
    current_mb = 0.0
    batch_mb_limit = batch_mb * 1024 * 1024  # convert to bytes (0 = disabled)

    for file in files:
        file_bytes = file.stat().st_size
        file_mb_str = f"{file_bytes / 1_048_576:.1f} MB"

        # Flush current batch if either limit would be exceeded
        would_exceed_count = batch_size > 0 and len(current_batch) >= batch_size
        would_exceed_mb = batch_mb_limit > 0 and current_mb + file_bytes > batch_mb_limit

        if current_batch and (would_exceed_count or would_exceed_mb):
            batches.append(current_batch)
            current_batch = []
            current_mb = 0.0

        current_batch.append(file)
        current_mb += file_bytes

    if current_batch:
        batches.append(current_batch)

    total = len(files)
    num_batches = len(batches)
    success = 0
    file_index = 0

    batch_label = (
        f"batch-size={batch_size}" if batch_size and not batch_mb else
        f"batch-mb={batch_mb}" if batch_mb and not batch_size else
        f"batch-size={batch_size}, batch-mb={batch_mb}" if batch_size and batch_mb else
        "no batching"
    )
    if num_batches > 1:
        console.print(f"[dim]Processing {total} files in {num_batches} batches ({batch_label})[/dim]")

    for batch_num, batch in enumerate(batches, 1):
        if num_batches > 1:
            batch_bytes = sum(f.stat().st_size for f in batch)
            console.print(
                f"\n[bold]Batch {batch_num}/{num_batches}[/bold] "
                f"[dim]({len(batch)} files, {batch_bytes / 1_048_576:.1f} MB)[/dim]"
            )

        for file in batch:
            file_index += 1
            # Copy to ingest_dir unless already inside it
            try:
                file.resolve().relative_to(ingest_dir.resolve())
                ingest_path = file
            except ValueError:
                dest = ingest_dir / file.name
                if dest.exists() and dest.resolve() != file.resolve():
                    stem, suffix = file.stem, file.suffix
                    counter = 1
                    while dest.exists():
                        dest = ingest_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                if not dest.exists():
                    shutil.copy2(file, dest)
                    console.print(f"  [dim]→ copied to {dest}[/dim]")
                ingest_path = dest

            console.print(f"[dim]({file_index}/{total})[/dim] Ingesting [bold]{file.name}[/bold]...")
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

        # Release parsed document memory between batches
        if num_batches > 1:
            gc.collect()

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


@app.command()
def related(
    paper: str = typer.Argument(..., help="Paper ID (graph node ID) or path to the source file."),
    db: Path = typer.Option(None, "--db", help="Path to the kuzu database directory."),
    strategy: str = typer.Option("all", "--strategy", help="Search strategy: topic|author|arxiv_id|all."),
    top_k: int = typer.Option(10, "--top-k", help="Number of results to return."),
    rerank: bool = typer.Option(True, "--rerank/--no-rerank", help="Re-rank by embedding similarity."),
    ingest_top: int = typer.Option(0, "--ingest", help="Ingest the top-N results into the database (0 = off)."),
) -> None:
    """Find arXiv papers related to a paper already in the graph.

    PAPER can be a graph node ID (16-char hex) or a file path that was
    previously ingested (the ID is derived from the file path).

    Uses the paper's topics, authors, and/or arXiv ID to query the arXiv
    API, then optionally re-ranks results by embedding similarity.

    \b
    Examples:
      pdf-rag related ca68451d8fe5107a
      pdf-rag related ~/papers/2301.04567.pdf --strategy topic --top-k 5
      pdf-rag related ca68451d8fe5107a --ingest 3
    """
    import hashlib

    from pdf_rag.arxiv import find_related
    from pdf_rag.config import DEFAULT_DB_PATH
    from pdf_rag.graph.store import GraphStore

    db_path = db or DEFAULT_DB_PATH
    if not Path(db_path).exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        raise typer.Exit(1)

    # Resolve paper_id — either raw ID or derive from file path
    maybe_path = Path(paper)
    if maybe_path.exists():
        paper_id = hashlib.sha1(str(maybe_path.resolve()).encode()).hexdigest()[:16]
    else:
        paper_id = paper

    store = GraphStore(db_path)

    embedder = None
    if rerank:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
            t = progress.add_task("Loading embedder for re-ranking...", total=None)
            from pdf_rag.ingestion.embedder import Embedder
            embedder = Embedder()
            progress.remove_task(t)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        t = progress.add_task("Searching arXiv...", total=None)
        results = find_related(
            paper_id=paper_id,
            store=store,
            strategy=strategy,
            top_k=top_k,
            rerank=rerank,
            embedder=embedder,
        )
        progress.remove_task(t)

    if not results:
        console.print("[yellow]No related papers found.[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"Related papers from arXiv (strategy={strategy})")
    table.add_column("#", style="dim", width=3)
    table.add_column("arXiv ID", style="cyan", no_wrap=True)
    table.add_column("Title", max_width=55)
    table.add_column("Authors", max_width=25, style="green")
    table.add_column("Year", width=6)
    table.add_column("Score", width=7, justify="right")

    for i, r in enumerate(results, 1):
        table.add_row(
            str(i),
            r.arxiv_id,
            r.title,
            ", ".join(r.authors[:2]) + (" et al." if len(r.authors) > 2 else ""),
            r.published[:4],
            f"{r.similarity_score:.3f}" if r.similarity_score else "—",
        )

    console.print(table)
    console.print(
        "\n[dim]Thank you to arXiv for use of its open access interoperability.[/dim]"
    )

    if ingest_top > 0:
        to_ingest = results[:ingest_top]
        console.print(f"\nIngesting top {len(to_ingest)} result(s)...")
        from pdf_rag.extraction.entities import EntityExtractor
        from pdf_rag.ingestion.embedder import Embedder as _Embedder
        from pdf_rag.pipeline import ingest_document
        from pdf_rag.config import DEFAULT_INGEST_DIR
        import urllib.request

        ingest_dir = DEFAULT_INGEST_DIR
        ingest_dir.mkdir(parents=True, exist_ok=True)
        _embedder = embedder or _Embedder()
        _extractor = EntityExtractor()

        for r in to_ingest:
            dest = ingest_dir / f"{r.arxiv_id}.pdf"
            if dest.exists():
                console.print(f"  [dim]already exists: {dest}[/dim]")
                continue
            try:
                console.print(f"  Downloading {r.arxiv_id}...")
                urllib.request.urlretrieve(r.pdf_url, dest)
                result = ingest_document(dest, db_path=db_path, embedder=_embedder, extractor=_extractor)
                console.print(
                    f"  [green]✓[/green] {r.title[:60]} "
                    f"({result.chunk_count} chunks)"
                )
            except Exception as e:
                console.print(f"  [red]✗[/red] {r.arxiv_id}: {e}")


if __name__ == "__main__":
    app()
