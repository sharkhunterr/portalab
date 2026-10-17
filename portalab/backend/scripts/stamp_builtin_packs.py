"""Stamps Portalab's own visual packs (spec 028): each pack's version follows its content.

The packs (``packs/builtin/<pack>/``) are the looks' and interfaces' source — edited by hand like any pack. A
release synchronises a pack whose files changed only when its version changed too: this sets every pack's
version to ``<release>+<fingerprint of its files>`` (``pack.json`` left out), so an edited pack gets a new
version and an untouched one keeps its own. Run from ``backend/`` after editing a pack:
``uv run python scripts/stamp_builtin_packs.py [--check]`` (``--check``: only say which would change).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "packs" / "builtin"
RELEASE = "1.0.0"


def fingerprint(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "pack.json"):
        digest.update(path.relative_to(folder).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()[:10]


def stamp(root: Path, *, check: bool) -> list[str]:
    changed = []
    for folder in sorted(p for p in root.iterdir() if (p / "pack.json").is_file()):
        manifest_path = folder / "pack.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = f"{RELEASE}+{fingerprint(folder)}"
        if manifest.get("version") == version:
            continue
        changed.append(f"{folder.name}: {manifest.get('version')} → {version}")
        if not check:
            manifest["version"] = version
            text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
            manifest_path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = stamp(args.root, check=args.check)
    print("\n".join(changed) or "every pack's version follows its content")
    if args.check and changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
