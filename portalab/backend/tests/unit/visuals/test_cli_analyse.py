"""028 (US8, FR-042): ``portalab visuals analyse`` — the portal's own analysis for a pack author, offline."""

import io
import json
from pathlib import Path

from portalab.modules.visuals.cli import analyse_command
from tests.unit.visuals.support import FakeInterfaces, tiny_pack, zip_of

EXAMPLES = Path(__file__).resolve().parents[4] / "examples" / "visual-packs"


def test_a_good_pack_passes_and_the_json_is_the_portal_s_report(tmp_path: Path) -> None:
    out = io.StringIO()
    assert analyse_command(EXAMPLES / "abysses", interfaces=FakeInterfaces(), out=out) == 0
    assert "0 blocking" in out.getvalue()
    out = io.StringIO()
    assert analyse_command(EXAMPLES / "nordlys", as_json=True, interfaces=FakeInterfaces(), out=out) == 0
    report = json.loads(out.getvalue())
    assert report["summary"]["publishable"] and report["summary"]["elements"] == 12


def test_a_blocking_finding_and_an_unreadable_pack(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(zip_of(tiny_pack(look="gold")))  # a built-in frame's key
    out = io.StringIO()
    assert analyse_command(bad, out=out) == 1
    assert "look.builtin" in out.getvalue()
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")
    assert analyse_command(broken, out=io.StringIO()) == 2
