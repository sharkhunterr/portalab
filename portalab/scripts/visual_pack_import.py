"""Import a visual pack folder into a running Portalab, through its API: zipped, uploaded, its scenes bound to
the boosters named, then published (the Review step's choices, made here).

    cd backend && uv run python ../scripts/visual_pack_import.py ../examples/visual-packs/mediacards \\
        --base https://127.0.0.1:8443 --login admin --password-file <file> \\
        [--bind mediacards=card_booster] [--insecure] [--dry-run]

``--bind <scene look>=<booster key>``: ``*`` for every looks booster, ``card_booster`` for every Mediacards
booster (issue 243), else a booster's product key. A version already published is left as it is. The password
is read from a file, never from the command line.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import sys
import zipfile

import httpx

API = "/api/v1"


def zipped(folder: pathlib.Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(folder).as_posix())
    return buffer.getvalue()


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("folder", type=pathlib.Path)
    args.add_argument("--base", required=True)
    args.add_argument("--login", required=True)
    args.add_argument("--password-file", type=pathlib.Path, required=True)
    args.add_argument("--bind", action="append", default=[], help="<scene look>=<booster key>")
    args.add_argument("--insecure", action="store_true", help="accept a self-signed certificate")
    args.add_argument("--dry-run", action="store_true")
    opts = args.parse_args()
    bindings = dict(item.split("=", 1) for item in opts.bind)
    package = zipped(opts.folder)
    print(f"pack   {opts.folder.name}: {len(package)} bytes, bindings {bindings or 'none'}")
    if opts.dry_run:
        return 0
    client = httpx.Client(base_url=opts.base.rstrip("/") + API, verify=not opts.insecure, timeout=120)
    password = opts.password_file.read_text(encoding="utf-8").strip()
    client.post("/auth/login", json={"login": opts.login, "password": password}).raise_for_status()
    token = next((c.value for c in client.cookies.jar if c.name.endswith("portalab_csrf")), None)
    if token:
        client.headers["X-CSRF-Token"] = token
    sent = client.post(
        "/admin/visuals/upload",
        params={"filename": f"{opts.folder.name}.zip"},
        content=package,
        headers={"Content-Type": "application/zip"},
    )
    sent.raise_for_status()
    pack, version = sent.json()["pack"], sent.json()["version"]
    detail = client.get(f"/admin/visuals/{pack}/{version}")
    detail.raise_for_status()
    found = detail.json()
    state = found.get("step") or (found.get("version") or {}).get("step")
    print(f"upload {pack} {version}: {'new' if sent.json()['new'] else 'known'} ({state})")
    if state == "published":
        return 0
    client.put(
        f"/admin/visuals/{pack}/{version}/draft",
        json={"economy": {}, "bindings": bindings, "confirmations": {}},
    ).raise_for_status()
    client.post(f"/admin/visuals/{pack}/{version}/publish", json={"economy": {}}).raise_for_status()
    print(f"publish {pack} {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
