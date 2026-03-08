"""Tests for the ArxivClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pdf_rag.arxiv import ArxivClient, ArxivResult


SAMPLE_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.04567v2</id>
    <title>Attention Is All You Need</title>
    <summary>We propose a new network architecture...</summary>
    <published>2017-06-12T00:00:00Z</published>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
    <category term="cs.LG"/>
    <link title="pdf" href="https://arxiv.org/pdf/2301.04567v2"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/1810.04805v2</id>
    <title>BERT: Pre-training of Deep Bidirectional Transformers</title>
    <summary>We introduce BERT...</summary>
    <published>2018-10-11T00:00:00Z</published>
    <author><name>Jacob Devlin</name></author>
    <link title="pdf" href="https://arxiv.org/pdf/1810.04805v2"/>
    <arxiv:primary_category term="cs.CL"/>
  </entry>
</feed>
"""


def _mock_response(text: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


class TestArxivResult:
    def test_fields_present(self) -> None:
        r = ArxivResult(
            arxiv_id="2301.04567",
            title="Test",
            authors=["Alice"],
            abstract="Abstract text.",
            published="2023-01-01",
            categories=["cs.CL"],
            pdf_url="https://arxiv.org/pdf/2301.04567",
            similarity_score=0.9,
        )
        assert r.arxiv_id == "2301.04567"
        assert r.similarity_score == 0.9

    def test_to_dict_keys(self) -> None:
        r = ArxivResult("id", "t", [], "a", "2023", [], "url", 0.5)
        d = r.to_dict()
        assert set(d.keys()) == {
            "arxiv_id", "title", "authors", "abstract",
            "published", "categories", "pdf_url", "similarity_score",
        }


class TestArxivClientParse:
    def test_parses_two_entries(self) -> None:
        client = ArxivClient()
        results = client._parse_atom(SAMPLE_ATOM)
        assert len(results) == 2

    def test_arxiv_id_extracted(self) -> None:
        client = ArxivClient()
        results = client._parse_atom(SAMPLE_ATOM)
        assert results[0].arxiv_id == "2301.04567"

    def test_authors_list(self) -> None:
        client = ArxivClient()
        results = client._parse_atom(SAMPLE_ATOM)
        assert results[0].authors == ["Ashish Vaswani", "Noam Shazeer"]

    def test_categories_parsed(self) -> None:
        client = ArxivClient()
        results = client._parse_atom(SAMPLE_ATOM)
        assert "cs.CL" in results[0].categories

    def test_pdf_url_extracted(self) -> None:
        client = ArxivClient()
        results = client._parse_atom(SAMPLE_ATOM)
        assert "pdf" in results[0].pdf_url

    def test_empty_feed_returns_empty(self) -> None:
        client = ArxivClient()
        empty = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        assert client._parse_atom(empty) == []


class TestArxivClientSearch:
    def test_search_by_terms_calls_api(self) -> None:
        client = ArxivClient()
        with patch("httpx.get", return_value=_mock_response(SAMPLE_ATOM)) as mock_get:
            results = client.search(terms=["transformer", "attention"], max_results=5)
        mock_get.assert_called_once()
        url, = mock_get.call_args.args
        assert "export.arxiv.org" in url
        assert len(results) == 2

    def test_search_by_arxiv_id(self) -> None:
        client = ArxivClient()
        with patch("httpx.get", return_value=_mock_response(SAMPLE_ATOM)):
            results = client.search(arxiv_id="2301.04567", max_results=5)
        assert len(results) == 2

    def test_search_requires_terms_or_id(self) -> None:
        client = ArxivClient()
        with pytest.raises(ValueError, match="terms.*arxiv_id"):
            client.search(max_results=5)

    def test_http_error_returns_empty(self) -> None:
        client = ArxivClient()
        err_resp = _mock_response("", 500)
        err_resp.raise_for_status.side_effect = Exception("500")
        with patch("httpx.get", return_value=err_resp):
            results = client.search(terms=["test"], max_results=5)
        assert results == []

    def test_rate_limit_respected(self) -> None:
        import time
        client = ArxivClient(min_interval=0.05)
        client._last_call = time.monotonic()  # simulate recent call
        with patch("httpx.get", return_value=_mock_response(SAMPLE_ATOM)):
            t0 = time.monotonic()
            client.search(terms=["test"], max_results=1)
            elapsed = time.monotonic() - t0
        assert elapsed >= 0.04  # slept at least min_interval
