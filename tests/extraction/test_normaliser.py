"""Tests for entity normaliser / deduplicator."""

from __future__ import annotations

import pytest

from pdf_rag.extraction.normaliser import normalise_authors, normalise_topics


class TestNormaliseAuthors:
    def test_empty_returns_empty(self) -> None:
        assert normalise_authors([]) == []

    def test_single_author_returned(self) -> None:
        result = normalise_authors(["Alice Smith"])
        assert len(result) == 1
        assert result[0]["canonical_name"] == "Alice Smith"

    def test_exact_duplicates_collapsed(self) -> None:
        result = normalise_authors(["Alice Smith", "Alice Smith", "Bob Jones"])
        names = [r["canonical_name"] for r in result]
        assert names.count("Alice Smith") == 1
        assert "Bob Jones" in names

    def test_abbreviated_name_merged(self) -> None:
        # "A. Smith" should merge with "Alice Smith"
        result = normalise_authors(["Alice Smith", "A. Smith"], threshold=0.7)
        assert len(result) == 1

    def test_distinct_names_kept_separate(self) -> None:
        result = normalise_authors(["Alice Smith", "Bob Jones", "Carol White"])
        assert len(result) == 3

    def test_canonical_name_is_longest_variant(self) -> None:
        # When merging variants, pick the most complete name
        result = normalise_authors(["A. Smith", "Alice Smith"], threshold=0.7)
        assert result[0]["canonical_name"] == "Alice Smith"

    def test_result_has_variants_key(self) -> None:
        result = normalise_authors(["Alice Smith", "A. Smith"], threshold=0.7)
        assert "variants" in result[0]

    def test_case_insensitive_dedup(self) -> None:
        result = normalise_authors(["alice smith", "Alice Smith"])
        assert len(result) == 1


class TestNormaliseTopics:
    def test_empty_returns_empty(self) -> None:
        assert normalise_topics([]) == []

    def test_single_topic_returned(self) -> None:
        result = normalise_topics(["graph neural network"])
        assert len(result) == 1
        assert result[0]["canonical_name"] == "graph neural network"

    def test_exact_duplicates_collapsed(self) -> None:
        result = normalise_topics(["transformer", "transformer", "attention mechanism"])
        names = [r["canonical_name"] for r in result]
        assert names.count("transformer") == 1

    def test_similar_topics_merged(self) -> None:
        result = normalise_topics(
            ["graph neural network", "graph neural networks"],
            threshold=0.85,
        )
        assert len(result) == 1

    def test_distinct_topics_kept_separate(self) -> None:
        result = normalise_topics(["transformer", "random forest", "bayesian inference"])
        assert len(result) == 3

    def test_result_has_required_keys(self) -> None:
        result = normalise_topics(["attention"])
        assert "canonical_name" in result[0]
        assert "variants" in result[0]

    def test_case_insensitive_dedup(self) -> None:
        result = normalise_topics(["Transformer", "transformer"])
        assert len(result) == 1
