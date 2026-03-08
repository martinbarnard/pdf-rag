"""Tests for LLM backend routing (Anthropic vs local OpenAI-compatible)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pdf_rag.llm import call_llm, list_local_models, probe_local


CONTEXT = "Transformers use self-attention. Vaswani et al., 2017."
QUERY = "What is self-attention?"


class TestCallLlmAnthropicBackend:
    def test_routes_to_anthropic_when_backend_is_anthropic(self) -> None:
        with patch("pdf_rag.llm._call_anthropic", return_value="answer") as mock:
            call_llm(CONTEXT, QUERY, backend="anthropic")
        mock.assert_called_once_with(CONTEXT, QUERY)

    def test_returns_string(self) -> None:
        with patch("pdf_rag.llm._call_anthropic", return_value="the answer"):
            result = call_llm(CONTEXT, QUERY, backend="anthropic")
        assert isinstance(result, str)
        assert result == "the answer"

    def test_anthropic_called_with_context_and_query(self) -> None:
        with patch("pdf_rag.llm._call_anthropic", return_value="ok") as mock:
            call_llm(CONTEXT, QUERY, backend="anthropic")
        mock.assert_called_once_with(CONTEXT, QUERY)

    def test_empty_context_still_calls_anthropic(self) -> None:
        with patch("pdf_rag.llm._call_anthropic", return_value="no docs") as mock:
            call_llm("", QUERY, backend="anthropic")
        mock.assert_called_once_with("", QUERY)


class TestCallLlmLocalBackend:
    def test_routes_to_local_when_backend_is_local(self) -> None:
        with patch("pdf_rag.llm._call_local", return_value="local answer") as mock:
            result = call_llm(CONTEXT, QUERY, backend="local")
        mock.assert_called_once_with(CONTEXT, QUERY)
        assert result == "local answer"

    def test_returns_string_from_local(self) -> None:
        with patch("pdf_rag.llm._call_local", return_value="local result"):
            result = call_llm(CONTEXT, QUERY, backend="local")
        assert isinstance(result, str)

    def test_empty_context_still_calls_local(self) -> None:
        with patch("pdf_rag.llm._call_local", return_value="fallback") as mock:
            call_llm("", QUERY, backend="local")
        mock.assert_called_once_with("", QUERY)


class TestCallLlmDefaultBackend:
    def test_default_backend_from_config(self) -> None:
        """call_llm with no backend arg reads from config."""
        with patch("pdf_rag.llm.LLM_BACKEND", "anthropic"):
            with patch("pdf_rag.llm._call_anthropic", return_value="ok") as mock:
                call_llm(CONTEXT, QUERY)
        mock.assert_called_once()

    def test_local_default_routes_to_local(self) -> None:
        with patch("pdf_rag.llm.LLM_BACKEND", "local"):
            with patch("pdf_rag.llm._call_local", return_value="ok") as mock:
                call_llm(CONTEXT, QUERY)
        mock.assert_called_once()

    def test_invalid_backend_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM backend"):
            call_llm(CONTEXT, QUERY, backend="unknown_backend")

    def test_auto_uses_local_when_probe_succeeds(self) -> None:
        with patch("pdf_rag.llm.probe_local", return_value=True):
            with patch("pdf_rag.llm._call_local", return_value="local") as mock:
                result = call_llm(CONTEXT, QUERY, backend="auto")
        mock.assert_called_once_with(CONTEXT, QUERY)
        assert result == "local"

    def test_auto_falls_back_to_anthropic_when_probe_fails(self) -> None:
        with patch("pdf_rag.llm.probe_local", return_value=False):
            with patch("pdf_rag.llm._call_anthropic", return_value="claude") as mock:
                result = call_llm(CONTEXT, QUERY, backend="auto")
        mock.assert_called_once_with(CONTEXT, QUERY)
        assert result == "claude"

    def test_auto_falls_back_when_local_raises(self) -> None:
        with patch("pdf_rag.llm.probe_local", return_value=True):
            with patch("pdf_rag.llm._call_local", side_effect=Exception("conn refused")):
                with patch("pdf_rag.llm._call_anthropic", return_value="fallback") as mock:
                    result = call_llm(CONTEXT, QUERY, backend="auto")
        mock.assert_called_once()
        assert result == "fallback"


class TestCallLocal:
    """Unit tests for _call_local using a mocked httpx response."""

    def test_call_local_posts_to_base_url(self) -> None:
        from pdf_rag.llm import _call_local

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "local model answer"}}]
        }

        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.llm.LOCAL_LLM_MODEL", "qwen2.5-7b-instruct"):
                with patch("httpx.post", return_value=mock_resp) as mock_post:
                    result = _call_local(CONTEXT, QUERY)

        assert result == "local model answer"
        assert mock_post.called
        call_kwargs = mock_post.call_args
        assert "http://localhost:1234" in call_kwargs[0][0]

    def test_call_local_includes_system_and_user_messages(self) -> None:
        from pdf_rag.llm import _call_local

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "answer"}}]
        }

        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.llm.LOCAL_LLM_MODEL", "test-model"):
                with patch("httpx.post", return_value=mock_resp) as mock_post:
                    _call_local(CONTEXT, QUERY)

        payload = mock_post.call_args[1]["json"]
        messages = payload["messages"]
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles

    def test_call_local_sends_model_name(self) -> None:
        from pdf_rag.llm import _call_local

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "answer"}}]
        }

        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.llm.LOCAL_LLM_MODEL", "my-model"):
                with patch("httpx.post", return_value=mock_resp) as mock_post:
                    _call_local(CONTEXT, QUERY)

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "my-model"

class TestProbeLocal:
    def test_returns_true_when_models_endpoint_responds(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": [{"id": "qwen3.5-9b"}]}
        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("httpx.get", return_value=mock_resp):
                assert probe_local() is True

    def test_returns_false_on_connection_error(self) -> None:
        import httpx
        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
                assert probe_local() is False

    def test_returns_false_on_timeout(self) -> None:
        import httpx
        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
                assert probe_local() is False

    def test_returns_false_on_http_error(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500")
        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("httpx.get", return_value=mock_resp):
                assert probe_local() is False


class TestListLocalModels:
    def test_returns_list_of_model_ids(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"id": "qwen3.5-9b"}, {"id": "mistral-7b"}]
        }
        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("httpx.get", return_value=mock_resp):
                models = list_local_models()
        assert models == ["qwen3.5-9b", "mistral-7b"]

    def test_returns_empty_list_when_server_unreachable(self) -> None:
        import httpx
        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
                assert list_local_models() == []

    def test_hits_correct_endpoint(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": []}
        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("httpx.get", return_value=mock_resp) as mock_get:
                list_local_models()
        assert mock_get.call_args[0][0] == "http://localhost:1234/v1/models"


    def test_call_local_empty_context(self) -> None:
        from pdf_rag.llm import _call_local

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "no context answer"}}]
        }

        with patch("pdf_rag.llm.LOCAL_LLM_BASE_URL", "http://localhost:1234"):
            with patch("pdf_rag.llm.LOCAL_LLM_MODEL", "test-model"):
                with patch("httpx.post", return_value=mock_resp):
                    result = _call_local("", QUERY)

        assert isinstance(result, str)
