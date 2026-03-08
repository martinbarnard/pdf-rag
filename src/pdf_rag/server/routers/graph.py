"""Graph traversal API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

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


@router.get("/graph/overview")
async def graph_overview(request: Request) -> dict:
    """Full graph snapshot for visualisation: all nodes and edges.

    Returns a Cytoscape.js-compatible elements format.
    """
    store = _store(request)

    nodes: list[dict] = []
    edges: list[dict] = []

    # Papers
    r = store.execute("MATCH (p:Paper) RETURN p.id, p.title, p.year")
    while r.has_next():
        row = r.get_next()
        nodes.append({"data": {"id": row[0], "label": row[1] or row[0], "type": "paper", "year": row[2]}})

    # Authors
    r = store.execute("MATCH (a:Author) RETURN a.id, a.canonical_name")
    while r.has_next():
        row = r.get_next()
        nodes.append({"data": {"id": row[0], "label": row[1] or row[0], "type": "author"}})

    # Topics
    r = store.execute("MATCH (t:Topic) RETURN t.id, t.canonical_name")
    while r.has_next():
        row = r.get_next()
        nodes.append({"data": {"id": row[0], "label": row[1] or row[0], "type": "topic"}})

    # AUTHORED edges
    r = store.execute("MATCH (a:Author)-[:AUTHORED]->(p:Paper) RETURN a.id, p.id")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"source": row[0], "target": row[1], "type": "AUTHORED"}})

    # DISCUSSES edges
    r = store.execute("MATCH (p:Paper)-[:DISCUSSES]->(t:Topic) RETURN p.id, t.id")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"source": row[0], "target": row[1], "type": "DISCUSSES"}})

    # CITES edges
    r = store.execute("MATCH (a:Paper)-[:CITES]->(b:Paper) RETURN a.id, b.id")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"source": row[0], "target": row[1], "type": "CITES"}})

    # RELATED_TO edges
    r = store.execute("MATCH (a:Topic)-[rel:RELATED_TO]->(b:Topic) RETURN a.id, b.id, rel.weight")
    while r.has_next():
        row = r.get_next()
        edges.append({"data": {"source": row[0], "target": row[1], "type": "RELATED_TO", "weight": row[2]}})

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
