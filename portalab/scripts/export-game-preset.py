#!/usr/bin/env python3
"""Issue 253 — capture a portal's game setup (rules, level curve and rewards, achievements, quests, campaigns,
play settings) as a preset Portalab ships: ``backend/src/portalab/app/game_presets/<name>.json``.

    scripts/export-game-preset.py --base https://portal:8443 --login admin --password-file FILE [--name lan]

Reads only (``GET /api/v1/admin/game/setup`` as an administrator); the password is read from a file, never
from the command line. A self-signed certificate is accepted (a LAN portal)."""

import argparse
import http.cookiejar
import json
import ssl
import sys
import urllib.request
from pathlib import Path

PRESETS = Path(__file__).resolve().parent.parent / "backend" / "src" / "portalab" / "app" / "game_presets"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--login", required=True)
    parser.add_argument("--password-file", required=True, type=Path)
    parser.add_argument("--name", default="lan")
    args = parser.parse_args()
    password = args.password_file.read_text(encoding="utf-8").strip()
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    api = args.base.rstrip("/") + "/api/v1"
    login = json.dumps({"login": args.login, "password": password}).encode()
    opener.open(urllib.request.Request(f"{api}/auth/login", data=login, headers={"Content-Type": "application/json"}))
    setup = json.load(opener.open(f"{api}/admin/game/setup"))
    if setup.get("format") != "portalab.game":
        print("not a game setup", file=sys.stderr)
        return 1
    target = PRESETS / f"{args.name}.json"
    target.write_text(json.dumps(setup, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sizes = {part: len(setup.get(part) or []) for part in ("rules", "achievements", "quests", "campaigns")}
    print(f"{target}: {len(setup.get('settings') or {})} settings, {sizes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
