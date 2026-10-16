"""Writes the fixtures of the visual packs' workflow journey (spec 028, T020): for an example pack and a
pack the analysis blocks, what the Admin API answers about a version — its report and its elements as the
interface draws them — so the frontend's e2e test walks the six steps on the real analysis.
Run from ``backend/``: ``uv run python scripts/e2e_visual_fixtures.py``."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.unit.visuals.support import FakeInterfaces, tiny_pack

from portalab.modules.visuals.analysis import analyse
from portalab.modules.visuals.service import VisualPacks
from portalab.modules.visuals.store import Files, read_folder

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "tests" / "e2e" / "visual-packs" / "fixtures"
SHA = "0123456789abcdef" * 4


def fixture(files: Files) -> dict:
    report = analyse(files, interfaces=FakeInterfaces())
    version = SimpleNamespace(sha256=SHA)
    pack = report["pack"]["id"]
    elements = VisualPacks.render_list(pack, version, report["elements"], admin=True)  # type: ignore[arg-type]
    return {"report": report, "elements": elements}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nordlys.json").write_text(
        json.dumps(fixture(read_folder(ROOT / "examples" / "visual-packs" / "nordlys")), indent=1) + "\n"
    )
    # the analysis stops it: a file it names is not there
    blocked = tiny_pack(pack="brouillon", look="tiny", render={"kind": "css", "css": ["missing.css"]})
    (OUT / "blocked.json").write_text(
        json.dumps(fixture(Files({k: v.encode() for k, v in blocked.items()})), indent=1) + "\n"
    )
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
