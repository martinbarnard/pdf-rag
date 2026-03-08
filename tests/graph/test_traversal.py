"""Tests for graph traversal queries."""

from __future__ import annotations

import pytest

from pdf_rag.graph.store import GraphStore


@pytest.fixture
def populated(tmp_path) -> GraphStore:
    """GraphStore seeded with a small connected graph for traversal tests."""
    s = GraphStore(tmp_path / "traversal.db")

    # Authors
    s.add_author("a1", "Alice Smith")
    s.add_author("a2", "Bob Jones")

    # Papers
    s.add_paper("p1", "Attention Is All You Need", year=2017)
    s.add_paper("p2", "BERT: Pre-training", year=2019)
    s.add_paper("p3", "GPT-3", year=2020)

    # Topics
    s.add_topic("t1", "transformer", canonical_name="Transformer")
    s.add_topic("t2", "self-attention", canonical_name="Self-Attention")
    s.add_topic("t3", "language model", canonical_name="Language Model")

    # Edges
    s.link_author_paper("a1", "p1")
    s.link_author_paper("a1", "p2")
    s.link_author_paper("a2", "p2")
    s.link_author_paper("a2", "p3")

    s.link_paper_topic("p1", "t1")
    s.link_paper_topic("p1", "t2")
    s.link_paper_topic("p2", "t1")
    s.link_paper_topic("p2", "t3")
    s.link_paper_topic("p3", "t3")

    s.link_paper_cites("p2", "p1")
    s.link_paper_cites("p3", "p1")

    # Related topics
    s.link_related_topics("t1", "t2", weight=0.9)

    return s


class TestPapersByAuthor:
    def test_returns_papers_for_known_author(self, populated: GraphStore) -> None:
        result = populated.papers_by_author("a1")
        ids = [r["id"] for r in result]
        assert "p1" in ids
        assert "p2" in ids

    def test_excludes_unrelated_papers(self, populated: GraphStore) -> None:
        result = populated.papers_by_author("a1")
        ids = [r["id"] for r in result]
        assert "p3" not in ids

    def test_unknown_author_returns_empty(self, populated: GraphStore) -> None:
        assert populated.papers_by_author("nobody") == []

    def test_result_has_required_keys(self, populated: GraphStore) -> None:
        result = populated.papers_by_author("a1")
        for row in result:
            assert "id" in row
            assert "title" in row
            assert "year" in row


class TestPapersByTopic:
    def test_returns_papers_for_topic(self, populated: GraphStore) -> None:
        result = populated.papers_by_topic("t1")
        ids = [r["id"] for r in result]
        assert "p1" in ids
        assert "p2" in ids

    def test_excludes_unrelated_papers(self, populated: GraphStore) -> None:
        result = populated.papers_by_topic("t2")
        ids = [r["id"] for r in result]
        assert "p2" not in ids

    def test_unknown_topic_returns_empty(self, populated: GraphStore) -> None:
        assert populated.papers_by_topic("t_unknown") == []


class TestRelatedTopics:
    def test_returns_related_topics(self, populated: GraphStore) -> None:
        result = populated.related_topics("t1")
        ids = [r["id"] for r in result]
        assert "t2" in ids

    def test_result_has_weight(self, populated: GraphStore) -> None:
        result = populated.related_topics("t1")
        assert result[0]["weight"] == pytest.approx(0.9)

    def test_no_relations_returns_empty(self, populated: GraphStore) -> None:
        assert populated.related_topics("t3") == []


class TestCoauthorNetwork:
    def test_returns_coauthors(self, populated: GraphStore) -> None:
        result = populated.coauthor_network("a1")
        ids = [r["id"] for r in result]
        assert "a2" in ids  # a1 and a2 both authored p2

    def test_excludes_self(self, populated: GraphStore) -> None:
        result = populated.coauthor_network("a1")
        ids = [r["id"] for r in result]
        assert "a1" not in ids

    def test_no_coauthors_returns_empty(self, populated: GraphStore) -> None:
        s = GraphStore.__new__(GraphStore)
        # Use populated but query an author with no collaborators
        result = populated.coauthor_network("a_solo")
        assert result == []


class TestCitationGraph:
    def test_returns_papers_citing_target(self, populated: GraphStore) -> None:
        result = populated.citing_papers("p1")
        ids = [r["id"] for r in result]
        assert "p2" in ids
        assert "p3" in ids

    def test_returns_papers_cited_by_source(self, populated: GraphStore) -> None:
        result = populated.cited_papers("p2")
        ids = [r["id"] for r in result]
        assert "p1" in ids

    def test_uncited_paper_returns_empty(self, populated: GraphStore) -> None:
        assert populated.citing_papers("p3") == []

    def test_result_has_required_keys(self, populated: GraphStore) -> None:
        result = populated.citing_papers("p1")
        for row in result:
            assert "id" in row
            assert "title" in row
