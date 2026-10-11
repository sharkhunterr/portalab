"""The backend serves the built SPA; client routes fall back to index.html, API 404s stay problems."""

from pathlib import Path

import httpx

from portalab.app.main import create_app


async def test_spa_is_served_with_client_side_fallback(tmp_path: Path, heads: set[str]) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>Portalab</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')")
    app = create_app(migration_heads=heads, static_dir=tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        assert "Portalab" in (await client.get("/")).text
        assert (await client.get("/assets/app.js")).text == "console.log('ok')"
        deep = await client.get("/media/some-client-route")
        assert deep.status_code == 200 and "Portalab" in deep.text
        api = await client.get("/api/v1/unknown")
        assert api.status_code == 404
        assert api.headers["content-type"].startswith("application/problem+json")
        assert (await client.get("/healthz")).json() == {"status": "ok"}
        # a file of a previous build is a 404, never the page taken for code; the page is never cached
        stale = await client.get("/assets/shaderRunner-OLDHASH.js")
        assert stale.status_code == 404 and "Portalab" not in stale.text
        assert "no-store" in (await client.get("/")).headers.get("cache-control", "")
        assert "no-store" in deep.headers.get("cache-control", "")


async def test_without_build_no_static_route_is_mounted(tmp_path: Path, heads: set[str]) -> None:
    app = create_app(migration_heads=heads, static_dir=tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/")).status_code == 404
