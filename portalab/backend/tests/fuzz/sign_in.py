"""Issue 401 — wait for the portal, make its Admin through the arrival wizard and sign in; prints the
session cookie and CSRF token as shell assignments (``TOKEN=…`` / ``CSRF=…``).

    uv run python -m tests.fuzz.sign_in http://127.0.0.1:8099
"""

import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from http.client import HTTPResponse


def call(url: str, body: dict[str, object] | None = None) -> HTTPResponse:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"content-type": "application/json"})  # noqa: S310 — a local test address
    response: HTTPResponse = urllib.request.urlopen(request, timeout=30)  # noqa: S310
    return response


def main() -> None:
    base = sys.argv[1].rstrip("/")
    for _ in range(90):
        try:
            call(f"{base}/api/v1/admin/first-run")
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(1)
    password = "Fuzz-" + secrets.token_hex(16)
    admin: dict[str, object] = {"login": "fuzz", "password": password, "settings": {}, "steps": {}}
    call(f"{base}/api/v1/admin/first-run", admin)
    signed = call(f"{base}/api/v1/auth/login", {"login": "fuzz", "password": password})
    cookies = signed.headers.get_all("set-cookie") or []
    # plain HTTP from the loopback (issue 395): the session goes as « portalab_session »
    token = next(c.split(";")[0].split("=", 1)[1] for c in cookies if c.startswith("portalab_session="))
    csrf = json.loads(signed.read())["csrf_token"]
    print(f"TOKEN={token}\nCSRF={csrf}")


if __name__ == "__main__":
    main()
