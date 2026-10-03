"""023 T031 — plugin routes are default-deny and permission-checked; pages hide their existence without
the permission; assets are images only (no traversal, strict CSP); page Markdown is sanitized; oversized
payloads are refused."""

import pytest
from httpx import AsyncClient

from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration


async def test_ui_bounds(pl: PlHarness, client: AsyncClient) -> None:
    source = pl.hello()
    (source / "assets" / "notes.txt").write_text("not an image")
    (source / "assets" / "evil.svg").write_text("<svg onload=alert(1)/>")
    with (source / "plugin.toml").open("a") as manifest:
        manifest.write("")
    page_md = (
        (source / "plugin.toml")
        .read_text()
        .replace(
            "A **declarative** page",
            "<script>alert(1)</script><img src=x onerror=alert(1)> A **declarative** page",
        )
    )
    (source / "plugin.toml").write_text(page_md)
    await pl.installed(source)
    assert (await client.get("/api/v1/plugins/hello/greetings/count")).status_code == 401
    await login(client, "ursula")
    assert (await client.get("/api/v1/plugins/hello/greetings/count")).status_code == 403
    assert (await client.get("/api/v1/plugins/hello/pages/main")).status_code == 404  # hidden
    assert (await client.get("/api/v1/plugins/pages")).json() == []
    await login(client, "boss")
    assert (await client.get("/api/v1/plugins/hello/undeclared")).status_code == 404
    page = (await client.get("/api/v1/plugins/hello/pages/main")).json()
    html = page["blocks"][0]["html"]
    assert "<script" not in html and "<img" not in html and "<strong>declarative</strong>" in html
    assert [b["kind"] for b in page["blocks"]] == ["markdown", "stat", "form"]
    assert {"plugin": "hello", "key": "main", "title_key": "plugin.hello:page.title"} in (
        await client.get("/api/v1/plugins/pages")
    ).json()
    logo = await client.get("/api/v1/plugins/hello/assets/logo.png")
    assert logo.status_code == 200 and logo.headers["content-security-policy"] == "default-src 'none'"
    for path in ("assets/notes.txt", "assets/evil.svg", "assets/../plugin.toml", "assets/%2e%2e/plugin.toml"):
        assert (await client.get(f"/api/v1/plugins/hello/{path}")).status_code == 404, path
    greeted = await client.post("/api/v1/plugins/hello/greet", json={"name": "Ada"})
    assert greeted.json() == {"state": "available", "message": "Hello, Ada!"}
    huge = await client.post("/api/v1/plugins/hello/greet", json={"name": "x" * 70_000})
    assert huge.status_code == 403
