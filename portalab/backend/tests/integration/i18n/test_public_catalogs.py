"""Issue 246 — before signing in (the arrival wizard, sign-in), the visitor reads the enabled languages and
the catalogs of those screens only, in the language asked for when enabled (else the portal's default)."""

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_public_catalogs(client: httpx.AsyncClient) -> None:
    answer = await client.get("/api/v1/i18n/public/languages")
    languages = answer.json()
    assert answer.status_code == 200, languages
    assert {"en", "fr"} <= {item["code"] for item in languages["items"]}
    french = await client.get("/api/v1/i18n/public/catalogs/account?lang=fr")
    assert french.status_code == 200 and french.json()["language"] == "fr"
    assert (
        french.json()["messages"]["auth.loginTitle"]
        != (
            (await client.get("/api/v1/i18n/public/catalogs/account?lang=en")).json()["messages"][
                "auth.loginTitle"
            ]
        )
    )
    unknown = await client.get("/api/v1/i18n/public/catalogs/account?lang=xx")
    assert unknown.json()["language"] == languages["default"]
    # any other catalog: the very same answer as any address without a session
    assert (await client.get("/api/v1/i18n/public/catalogs/admin?lang=fr")).status_code == 401
    assert (await client.get("/api/v1/i18n/catalogs/account?lang=fr")).status_code == 401
