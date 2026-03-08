"""One-off script: re-derive titles for all Paper nodes using the same
logic as the pipeline (docling title → first section heading → filename stem).

Run with the server STOPPED (kuzu allows only one writer at a time):

    uv run python scripts/fix_titles.py

Prints a summary of changes made.
"""

from __future__ import annotations

from pathlib import Path

from pdf_rag.config import DEFAULT_DB_PATH
from pdf_rag.graph.store import GraphStore
from pdf_rag.ingestion.parser import parse_document


def _derive_title(file_path: Path) -> str | None:
    """Return a fresh title for the file, or None if the file is missing."""
    if not file_path.exists():
        return None
    try:
        doc = parse_document(file_path)
    except Exception as exc:
        print(f"  parse error: {exc}")
        return None
    return (
        doc.title
        or (doc.sections[0]["heading"] if doc.sections and doc.sections[0]["heading"] else "")
        or file_path.stem
    )


def main() -> None:
    store = GraphStore(DEFAULT_DB_PATH)

    r = store.execute("MATCH (p:Paper) RETURN p.id, p.title, p.file_path")
    rows: list[tuple[str, str, str]] = []
    while r.has_next():
        row = r.get_next()
        rows.append((row[0], row[1], row[2]))

    if not rows:
        print("No papers in the database. Re-ingest documents first.")
        return

    print(f"Found {len(rows)} papers.\n")
    updated = skipped = missing = 0

    for paper_id, old_title, file_path_str in rows:
        fp = Path(file_path_str) if file_path_str else None
        if not fp:
            print(f"[SKIP] {paper_id[:12]}  — no file_path stored")
            skipped += 1
            continue

        new_title = _derive_title(fp)
        if new_title is None:
            print(f"[MISS] {paper_id[:12]}  — file not found: {fp}")
            missing += 1
            continue

        if new_title == old_title:
            print(f"[OK]   {paper_id[:12]}  {old_title!r}")
            skipped += 1
            continue

        store.execute(
            "MATCH (p:Paper {id: $id}) SET p.title = $title",
            {"id": paper_id, "title": new_title},
        )
        print(f"[FIX]  {paper_id[:12]}  {old_title!r}  →  {new_title!r}")
        updated += 1

    print(f"\nDone. updated={updated}  unchanged={skipped}  missing={missing}")


if __name__ == "__main__":
    main()
