"""Graph traversal API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["graph"])


def _store(request: Request):
    from pdf_rag.graph.store import GraphStore
    return GraphStore(request.app.state.db_path)


@router.get("/authors/{author_id}/papers")
async def papers_by_author(author_id: str, request: Request) -> list[dict]:
    """All papers authored by the given author."""
    return _store(request).papers_by_author(author_id)


@router.get("/authors/{author_id}/coauthors")
async def coauthors(author_id: str, request: Request) -> list[dict]:
    """All co-authors of the given author."""
    return _store(request).coauthor_network(author_id)


@router.get("/topics/{topic_id}/papers")
async def papers_by_topic(topic_id: str, request: Request) -> list[dict]:
    """All papers that discuss the given topic."""
    return _store(request).papers_by_topic(topic_id)


@router.get("/topics/{topic_id}/related")
async def related_topics(topic_id: str, request: Request) -> list[dict]:
    """Topics related to the given topic."""
    return _store(request).related_topics(topic_id)


@router.get("/papers/{paper_id}/citing")
async def citing_papers(paper_id: str, request: Request) -> list[dict]:
    """Papers that cite the given paper."""
    return _store(request).citing_papers(paper_id)


@router.get("/papers/{paper_id}/cited")
async def cited_papers(paper_id: str, request: Request) -> list[dict]:
    """Papers cited by the given paper."""
    return _store(request).cited_papers(paper_id)


@router.get("/papers/{paper_id}")
async def paper_detail(paper_id: str, request: Request) -> dict:
    """Full detail for a single paper: metadata + authors + topics + citation counts."""
    store = _store(request)

    r = store.execute(
        "MATCH (p:Paper {id: $id}) RETURN p.id, p.title, p.abstract, p.year, p.doi, p.file_path",
        {"id": paper_id},
    )
    if not r.has_next():
        raise HTTPException(status_code=404, detail="Paper not found")
    row = r.get_next()
    paper = {
        "id": row[0], "title": row[1], "abstract": row[2],
        "year": row[3], "doi": row[4], "file_path": row[5],
    }

    ar = store.execute(
        "MATCH (a:Author)-[:AUTHORED]->(p:Paper {id: $id}) RETURN a.id, a.canonical_name",
        {"id": paper_id},
    )
    authors = []
    while ar.has_next():
        r2 = ar.get_next()
        authors.append({"id": r2[0], "canonical_name": r2[1]})

    tr = store.execute(
        "MATCH (p:Paper {id: $id})-[:DISCUSSES]->(t:Topic) RETURN t.id, t.canonical_name",
        {"id": paper_id},
    )
    topics = []
    while tr.has_next():
        r2 = tr.get_next()
        topics.append({"id": r2[0], "canonical_name": r2[1]})

    cr = store.execute(
        "MATCH (a:Paper)-[:CITES]->(p:Paper {id: $id}) RETURN count(a)",
        {"id": paper_id},
    )
    cited_by_count = cr.get_next()[0] if cr.has_next() else 0

    cr2 = store.execute(
        "MATCH (p:Paper {id: $id})-[:CITES]->(b:Paper) RETURN count(b)",
        {"id": paper_id},
    )
    cites_count = cr2.get_next()[0] if cr2.has_next() else 0

    return {**paper, "authors": authors, "topics": topics, "cited_by": cited_by_count, "cites": cites_count}


@router.get("/graph/overview")
async def graph_overview(request: Request) -> dict:
    """Full graph snapshot for visualisation: all nodes and edges.

    Returns a Cytoscape.js-compatible elements format.
    """
    store = _store(request)

    nodes: list[dict] = []
    edges: list[dict] = []

    r = store.execute("MATCH (p:Paper) RETURN p.id, p.title, p.year, p.doi")
    while r.has_next():
        row = r.get_next()
        nodes.append({"data": {
            "id": row[0], "label": row[1] or row[0],
            "type": "Paper", "year": row[2], "doi": row[3] or "",
        }})

    r = store.execute("MATCH (a:Author) RETURN a.id, a.canonical_name")
    while r.has_next():
        row = r.get_next()
        nodes.append({"data": {"id": row[0], "label": row[1] or row[0], "type": "Author"}})

    r = store.execute("MATCH (t:Topic) RETURN t.id, t.canonical_name")
    while r.has_next():
        row = r.get_next()
        nodes.append({"data": {"id": row[0], "label": row[1] or row[0], "type": "Topic"}})

    r = store.execute("MATCH (a:Author)-[:AUTHORED]->(p:Paper) RETURN a.id, p.id")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"id": f"au-{row[0]}-{row[1]}", "source": row[0], "target": row[1], "type": "AUTHORED"}})

    r = store.execute("MATCH (p:Paper)-[:DISCUSSES]->(t:Topic) RETURN p.id, t.id")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"id": f"di-{row[0]}-{row[1]}", "source": row[0], "target": row[1], "type": "DISCUSSES"}})

    r = store.execute("MATCH (a:Paper)-[:CITES]->(b:Paper) RETURN a.id, b.id")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"id": f"ci-{row[0]}-{row[1]}", "source": row[0], "target": row[1], "type": "CITES"}})

    r = store.execute("MATCH (a:Topic)-[rel:RELATED_TO]->(b:Topic) RETURN a.id, b.id, rel.weight")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"id": f"rt-{row[0]}-{row[1]}", "source": row[0], "target": row[1], "type": "RELATED_TO", "weight": row[2]}})

    return {"nodes": nodes, "edges": edges}


@router.get("/stats")
async def stats(request: Request) -> dict:
    """Graph database statistics."""
    store = _store(request)
    result = {}
    for label, key in [("Paper", "papers"), ("Author", "authors"), ("Topic", "topics"),
                       ("Chunk", "chunks"), ("Institution", "institutions"), ("Venue", "venues")]:
        r = store.execute(f"MATCH (n:{label}) RETURN count(n)")
        result[key] = r.get_next()[0]
    return result
