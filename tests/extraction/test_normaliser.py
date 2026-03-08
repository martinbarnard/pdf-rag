"""Tests for entity normaliser / deduplicator."""

from __future__ import annotations

import pytest

from pdf_rag.extraction.normaliser import clean_topic, normalise_authors, normalise_topics


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


class TestCleanTopic:
    def test_strips_unmatched_open_paren(self) -> None:
        assert clean_topic("Tiny Recursive Model (Trm") == "Tiny Recursive Model"

    def test_keeps_balanced_parens(self) -> None:
        result = clean_topic("Hierarchical Reasoning Model (HRM)")
        assert result == "Hierarchical Reasoning Model (Hrm)"

    def test_collapses_whitespace(self) -> None:
        assert clean_topic("  graph   neural   network  ") == "Graph Neural Network"

    def test_strips_surrounding_punctuation(self) -> None:
        assert clean_topic('"attention mechanism"') == "Attention Mechanism"

    def test_empty_after_clean_returns_empty(self) -> None:
        assert clean_topic("(") == ""
        assert clean_topic("  ") == ""

    def test_short_token_rejected(self) -> None:
        assert clean_topic("AI") == ""   # 2 chars < MIN_TOPIC_LEN=3

    def test_pure_numeric_rejected(self) -> None:
        assert clean_topic("42") == ""


class TestNormaliseTopics:
    def test_empty_returns_empty(self) -> None:
        assert normalise_topics([]) == []

    def test_single_topic_returned(self) -> None:
        result = normalise_topics(["graph neural network"])
        assert len(result) == 1

    def test_exact_duplicates_collapsed(self) -> None:
        result = normalise_topics(["transformer", "transformer", "attention mechanism"])
        names = [r["canonical_name"] for r in result]
        # clean_topic title-cases everything
        assert names.count("Transformer") == 1

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

    def test_abbreviation_merged_with_expansion(self) -> None:
        # "HRM" should merge with "Hierarchical Reasoning Model (HRM)"
        result = normalise_topics([
            "Hierarchical Reasoning Model (HRM)",
            "HRM",
        ])
        assert len(result) == 1
        canonical = result[0]["canonical_name"]
        # canonical should be the longer, more descriptive form
        assert "Hierarchical" in canonical or "Hrm" in canonical

    def test_truncated_parens_cleaned_and_merged(self) -> None:
        # GLiNER truncation: "(Trm" unclosed — should still merge with "TRM"
        result = normalise_topics([
            "Tiny Recursive Model (Trm",
            "TRM",
        ])
        assert len(result) == 1

    def test_expansion_and_abbreviation_separate_inputs(self) -> None:
        # Full expansion + bare abbreviation + truncated form all → one cluster
        result = normalise_topics([
            "Hierarchical Reasoning Model (HRM)",
            "HRM",
            "Hierarchical Reasoning Model (Hrm",  # truncated
        ])
        assert len(result) == 1
