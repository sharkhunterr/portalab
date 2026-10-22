"""Import a folder of wiki pages (markdown with a small header) into a running Portalab, through its API.

Each file starts with a header between two ``---`` lines (``slug``, ``title``, ``position``, optional
``parent`` — a slug, or ``none`` for a top page —, ``help_keys`` and ``tags`` as ``[a, b]``), then the
page's markdown. A page is found by its slug: created when missing, updated when its title, text, tags or
help keys changed, left alone otherwise; then published and put in its place under its parent. Pages are
readable by everyone who may read the wiki and by the assistant.

    cd backend && uv run python ../scripts/wiki_import.py ../docs/member-guide/fr \\
        --base https://127.0.0.1:8443 --login admin --password-file <file> [--currency Xenocoins] \\
        [--insecure] [--dry-run]

The password is read from a file, never from the command line.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Any

import httpx

API = "/api/v1"


def parse(path: pathlib.Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"{path.name}: no header")
    head, body = text[4:].split("\n---\n", 1)
    page: dict[str, Any] = {"body_md": body.strip() + "\n", "help_keys": [], "tags": [], "parent": None}
    for line in head.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        value = value.split("  #", 1)[0].strip()
        if value.startswith("[") and value.endswith("]"):
            page[key] = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
        elif key == "position":
            page[key] = int(value)
        else:
            page[key] = value.strip("'\"")
    for key in ("slug", "title", "position"):
        if key not in page:
            raise SystemExit(f"{path.name}: no {key}")
    return page


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("folder", type=pathlib.Path)
    args.add_argument("--base", required=True)
    args.add_argument("--login", required=True)
    args.add_argument("--password-file", type=pathlib.Path, required=True)
    args.add_argument("--language", default="fr")
    args.add_argument("--insecure", action="store_true", help="accept a self-signed certificate")
    args.add_argument("--currency", help="the site's currency name, written instead of « Coins »")
    args.add_argument("--dry-run", action="store_true")
    opts = args.parse_args()
    pages = [parse(p) for p in sorted(opts.folder.glob("*.md"))]
    parents = {p["slug"]: p["parent"] for p in pages}

    def depth(slug: str | None) -> int:  # a parent is always imported before its pages
        return 0 if parents.get(slug or "") in (None, "none") else 1 + depth(parents[slug or ""])

    pages.sort(key=lambda p: (depth(p["slug"]), p["position"]))
    if opts.currency:  # the guide says « Coins », the default name; a site may call it otherwise
        for page in pages:
            for key in ("title", "body_md"):
                page[key] = re.sub(r"\bCoins\b", opts.currency, page[key])
    client = httpx.Client(base_url=opts.base.rstrip("/") + API, verify=not opts.insecure, timeout=120)
    password = opts.password_file.read_text(encoding="utf-8").strip()
    client.post("/auth/login", json={"login": opts.login, "password": password}).raise_for_status()
    # writes carry the session's CSRF token, as the portal's own pages do
    token = next((c.value for c in client.cookies.jar if c.name.endswith("portalab_csrf")), None)
    if token:
        client.headers["X-CSRF-Token"] = token
    ids: dict[str, str] = {}
    for page in pages:
        # no parent named: under the top page of the folder (the one whose parent is « none »)
        parent_slug = page["parent"] or next((p["slug"] for p in pages if p["parent"] == "none"), None)
        parent_slug = None if parent_slug in ("none", page["slug"]) else parent_slug
        parent_id = ids.get(parent_slug) if parent_slug else None
        body = {
            "title": page["title"],
            "body_md": page["body_md"],
            "slug": page["slug"],
            "parent_id": parent_id,
            "tags": page["tags"],
            "help_keys": page["help_keys"],
            "audience": {"mode": "all", "refs": []},
            "readable_by_ai": True,
            "language": opts.language,
            "publish": True,
        }
        found = client.get(f"/wiki/pages/{page['slug']}")
        if found.status_code == 404:
            action = "create"
            if not opts.dry_run:
                found = client.post("/wiki/pages", json={**body, "change_note": "Guide du membre"})
                found.raise_for_status()
        else:
            found.raise_for_status()
            current = found.json()
            same = (
                current["title"] == body["title"]
                and current["body_md"].strip() == body["body_md"].strip()
                and sorted(current["tags"]) == sorted(body["tags"])
                and sorted(current["help_keys"]) == sorted(body["help_keys"])
            )
            action = "same" if same else "update"
            if action == "update" and not opts.dry_run:
                found = client.put(
                    f"/wiki/pages/{current['id']}",
                    json={**body, "base_version": current["version"], "change_note": "Guide du membre"},
                )
                found.raise_for_status()
        view = found.json() if found.status_code < 400 else {}
        if opts.dry_run:
            print(f"{action:6} {page['slug']}")
            ids[page["slug"]] = view.get("id", page["slug"])
            continue
        ids[page["slug"]] = view["id"]
        if view["status"] != "published":
            client.post(f"/wiki/pages/{view['id']}/publish").raise_for_status()
        if view["parent_id"] != parent_id or view["position"] != page["position"]:
            client.post(
                f"/wiki/pages/{view['id']}/move", json={"parent_id": parent_id, "position": page["position"]}
            ).raise_for_status()
        print(f"{action:6} {page['slug']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
