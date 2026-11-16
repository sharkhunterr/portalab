"""Issue 469 — the nightly suite's portal, made ready: its Admin through the arrival wizard, then (once the
demo data is in) every product of the shop given to that Admin, the way an administrator gives one (a
grant, confirmed) — so each interface, widget, option and statistic can be tried as a member who owns it.
A demo member who owns nothing stays for the locked side.

    uv run python -m tests.nightly.prepare admin BASE STATE_FILE
    uv run python -m tests.nightly.prepare grant BASE STATE_FILE

The state file (0600) holds the accounts' credentials for the browser; it is never printed.
"""

import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


class Client:
    """A browser-like session: cookies kept, the CSRF token sent back on every change."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.csrf = ""

    def call(self, method: str, path: str, body: object | None = None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"content-type": "application/json"}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        request = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers, method=method)  # noqa: S310 — a local test address
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, raw.decode(errors="replace")

    def sign_in(self, login: str, password: str) -> None:
        status, body = self.call("POST", "/api/v1/auth/login", {"login": login, "password": password})
        if status != 200:
            sys.exit(f"could not sign in as {login}: {status}")
        self.csrf = body["csrf_token"]


def wait(base: str) -> None:
    for _ in range(120):
        try:
            urllib.request.urlopen(f"{base}/healthz", timeout=5)  # noqa: S310  # nosec B310 — http(s) checked in main
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(1)
    sys.exit("the portal did not start")


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as out:
        json.dump(state, out, indent=2)


def make_admin(base: str, state_file: Path) -> None:
    wait(base)
    password = "N9-" + secrets.token_hex(16)  # never the login inside (issue 406 refuses it)
    client = Client(base)
    admin = {"login": "nightly", "password": password, "settings": {}, "steps": {}}
    status, body = client.call("POST", "/api/v1/admin/first-run", admin)
    if status not in (200, 201):
        sys.exit(f"the arrival wizard refused the Admin: {status} {body}")
    write_state(state_file, {"base": base, "admin": {"login": "nightly", "password": password}})


def _demo_members(users_file: Path) -> dict[str, dict[str, str]]:
    """The demo members and their passwords, from the seed's credentials file (« login<TAB>password »)."""
    if not users_file.is_file():
        return {}
    members = {}
    for line in users_file.read_text(encoding="utf-8").splitlines():
        login, _, password = line.partition("\t")
        if login and password:
            members[login] = {"login": login, "password": password}
    return members


# who signs in on which screen: each device its own account (the dashboard is the member's own, the journeys
# of the three devices run side by side); « member » owns nothing — the shop's locked side
ACCOUNTS = {"desktop": "nightly", "phone": "alice", "tablet": "bruno", "member": "chloe"}
OWNERS = ("desktop", "phone", "tablet")


def grant_everything(base: str, state_file: Path) -> None:
    wait(base)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    accounts = {"nightly": state["admin"], **_demo_members(state_file.parent / "demo-users.txt")}
    admin = Client(base)
    admin.sign_in(state["admin"]["login"], state["admin"]["password"])
    _, products = admin.call("GET", "/api/v1/admin/marketplace/products")
    available = [p["key"] for p in products if p.get("state") == "available"]  # one switched off is not given
    resolved: dict[str, dict[str, str]] = {}
    for device, login in ACCOUNTS.items():
        account = accounts.get(login)
        if account is None:
            sys.exit(f"no credentials for {login} (did the demo seed run?)")
        resolved[device] = account
        if device not in OWNERS:
            continue
        member = Client(base)
        member.sign_in(account["login"], account["password"])
        _, me = member.call("GET", "/api/v1/me")
        _, mine = member.call("GET", "/api/v1/me/marketplace/owned")
        owned = {o["product_key"] for o in mine}
        given, refused = len(owned & set(available)), []
        for key in available:
            if key in owned:
                continue
            body: dict[str, Any] = {"user_id": me["id"], "product": key, "reason": "nightly regression suite"}
            status, answer = admin.call("POST", "/api/v1/admin/marketplace/grants", body)
            asked = isinstance(answer, dict) and answer.get("code") == "authz.confirmation_required"
            if status == 409 and asked:
                token = answer.get("confirmation") or (answer.get("extensions") or {}).get("confirmation")
                status, answer = admin.call(
                    "POST", "/api/v1/admin/marketplace/grants", {**body, "confirmation": token}
                )
            code = answer.get("code") if isinstance(answer, dict) else None
            if status == 201 or code == "marketplace.already_owned":
                given += 1  # (a bundle given before brought it already)
            else:
                refused.append(f"{key}: {status} {code or answer}")
        sys.stdout.write(f"{login}: {given} of {len(available)} products owned\n")
        for line in refused[:20]:
            sys.stdout.write(f"  not granted — {line}\n")
    write_state(state_file, {**state, "accounts": resolved, "products": [p["key"] for p in products]})
    write_matrix(base, resolved, state_file.parent / "matrix.json")


def write_matrix(base: str, accounts: dict[str, dict[str, str]], path: Path) -> None:
    """What the browser's journeys go over, known before they are listed (a test is declared, not found):
    the widgets an owner may place with their settings, the packs' add-ons, and what the shop keeps locked
    for a member owning nothing."""
    owner = Client(base)
    owner.sign_in(accounts["desktop"]["login"], accounts["desktop"]["password"])
    _, catalog = owner.call("GET", "/api/v1/dashboard/catalog")
    _, active = owner.call("GET", "/api/v1/visuals/active")
    member = Client(base)
    member.sign_in(accounts["member"]["login"], accounts["member"]["password"])
    _, locked = member.call("GET", "/api/v1/dashboard/locked-options")
    addons = [
        {"look": e["look"], "for": (e.get("widget") or {}).get("for"), "product": e.get("product")}
        for e in active["elements"]
        if e.get("type") == "widget_option" and not (e.get("widget") or {}).get("setting")
    ]
    looks: dict[str, list[str]] = {}
    for element in active["elements"]:
        if element.get("look"):
            looks.setdefault(element["type"], []).append(element["look"])
    matrix = {"widgets": catalog, "addons": addons, "locked": locked["locked"], "looks": looks}
    path.write_text(json.dumps(matrix, indent=1), encoding="utf-8")


def main() -> None:
    command, base, state_file = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    if not base.startswith(("http://", "https://")):
        sys.exit("the portal's address is an http(s) one")
    if command == "admin":
        make_admin(base, state_file)
    elif command == "grant":
        grant_everything(base, state_file)
    else:
        sys.exit(f"unknown command {command}")


if __name__ == "__main__":
    main()
