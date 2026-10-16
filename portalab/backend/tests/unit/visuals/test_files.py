"""028 (FR-024): a pack's file is served inert — opening it runs nothing, no other site reads it, its type
comes from its extension, a version not validated yet is never cached."""

from pathlib import Path

import pytest

from portalab.core.errors import NotFound
from portalab.modules.visuals.api.routes import _file
from portalab.modules.visuals.sandbox import HEADERS, POLICY


def test_pack_files_are_inert(tmp_path: Path) -> None:
    svg = tmp_path / "logo.svg"
    svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
    response = _file(svg, live=True)
    assert response.media_type == "image/svg+xml"
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "immutable" in response.headers["cache-control"]
    script = tmp_path / "nav.js"
    script.write_text("export default () => {}")
    served = _file(script, live=False)
    assert (
        served.headers["content-disposition"] == "attachment"
        and "no-store" in served.headers["cache-control"]
    )
    unknown = tmp_path / "x.bin"
    unknown.write_bytes(b"\0")
    assert _file(unknown, live=True).headers["content-disposition"] == "attachment"
    with pytest.raises(NotFound):
        _file(None, live=True)


def test_the_sandbox_reaches_nothing() -> None:
    assert "connect-src 'none'" in POLICY and "form-action 'none'" in POLICY
    assert "frame-ancestors 'self'" in POLICY and HEADERS["Cache-Control"] == "no-store"
