from __future__ import annotations

import httpx

from rewind.main import create_app


async def test_health_ok() -> None:
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "density" in body["models"]


async def test_unknown_route_error_envelope() -> None:
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "http_error"
