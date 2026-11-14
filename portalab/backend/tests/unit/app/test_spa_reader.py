"""#21 — the book reader's page gets its own content security policy (inline styles and ``blob:`` frames
for the EPUB's layout, still no script but the portal's); every other page keeps the strict one."""

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from portalab.app.spa import READER_CSP, SPAStaticFiles

pytestmark = pytest.mark.unit
OBJECT = "01a108ce-d539-7a94-a035-c9b33106596f"


def test_only_the_reader_page_relaxes_the_policy(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>Portalab</title>")
    app = Starlette()
    app.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
    client = TestClient(app)
    reader = client.get(f"/media/{OBJECT}/read")
    assert reader.status_code == 200 and reader.headers["content-security-policy"] == READER_CSP
    assert "script-src 'self';" in READER_CSP and "unsafe-eval" not in READER_CSP
    for path in (f"/media/{OBJECT}", f"/media/{OBJECT}/watch", "/media/x/read"):
        assert "content-security-policy" not in client.get(path).headers


def test_the_retro_page_runs_the_emulator_isolated(tmp_path: Path) -> None:
    """Issue 419: the game's page lets the library's emulator compile and run its cores (from the portal
    only) and is isolated from other origins, for the cores that share memory between threads."""
    (tmp_path / "index.html").write_text("<!doctype html><title>Portalab</title>")
    app = Starlette()
    app.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
    client = TestClient(app)
    play = client.get(f"/media/{OBJECT}/play")
    assert play.status_code == 200
    policy = play.headers["content-security-policy"]
    assert "script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval' blob:;" in policy
    assert "connect-src 'self' blob: data:;" in policy and "frame-ancestors 'none'" in policy
    assert play.headers["cross-origin-embedder-policy"] == "require-corp"
    assert play.headers["cross-origin-opener-policy"] == "same-origin"
    for path in (f"/media/{OBJECT}", "/media/x/play", f"/media/{OBJECT}/play/more"):
        assert "cross-origin-embedder-policy" not in client.get(path).headers
