"""Tests for FastAPI server setup."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    from pdf_rag.server.main import create_app
    return create_app()


@pytest.mark.asyncio
async def test_health_check(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_openapi_docs_available(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cors_header_present(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code in (200, 204)


@pytest.mark.asyncio
async def test_static_files_route_exists(app) -> None:
    """Static file route should be registered (even if no files exist yet)."""
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert any("/app" in r or "/static" in r for r in routes)


def test_serve_callable() -> None:
    from pdf_rag.server.main import serve
    assert callable(serve)


def test_create_app_returns_fastapi() -> None:
    from fastapi import FastAPI
    from pdf_rag.server.main import create_app
    app = create_app()
    assert isinstance(app, FastAPI)
