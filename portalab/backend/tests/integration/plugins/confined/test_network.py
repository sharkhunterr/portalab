"""030 T039 (US5, SC-008) — a plugin's outgoing calls go through Portalab: only to the hosts it lists, never
to a private address unless listed so, connected to the address Portalab resolved, without redirects; its
secret settings are added by Portalab and never reach the plugin (not in what it gets back, not in logs)."""

import logging
from typing import Any

import httpx
import pytest
from tests.integration.plugins.conftest import PlHarness

from portalab.core.secrets import SecretBox
from portalab.core.time import utc_now
from portalab.modules.plugins.confined.host import Denied
from portalab.modules.plugins.confined.network import Network, is_public
from portalab.modules.plugins.manifest.schema import validate
from portalab.modules.plugins.models import SecretSetting

SECRET = "s3cr3t-value-for-the-test"
MANIFEST = validate(
    {
        "schema_version": 2,
        "key": "weather",
        "name": "Weather",
        "version": "1.0.0",
        "entry_point": "weather_plugin:register",
        "capabilities": {
            "network": {
                "hosts": [
                    {"host": "api.example.org"},
                    {"host": "lan.example.org", "private": True},
                    {"host": "rebind.example.org"},
                ]
            }
        },
        "settings": [
            {
                "name": "api_key",
                "type": "string",
                "default": "",
                "secret": True,
                "inject": {"host": "api.example.org", "header": "X-Api-Key"},
            }
        ],
    }
)
ADDRESSES = {
    "api.example.org": ["93.184.215.14"],
    "lan.example.org": ["192.168.1.20"],
    "rebind.example.org": ["10.0.0.5"],
}


def test_public_addresses() -> None:
    assert is_public("93.184.215.14")
    for private in (
        "127.0.0.1",
        "10.1.2.3",
        "192.168.1.1",
        "169.254.169.254",
        "::1",
        "fd00::1",
        "::ffff:127.0.0.1",
        "0.0.0.0",
    ):
        assert not is_public(private), private


@pytest.fixture
async def network(pl: PlHarness) -> tuple[Network, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/"})
        return httpx.Response(
            200, json={"ok": True, "echo": dict(request.headers)}, headers={"set-cookie": "x=1"}
        )

    async def resolve(host: str, port: int) -> list[str]:
        return ADDRESSES.get(host, [])

    box = SecretBox(b"t" * 32)
    async with pl.database.unit_of_work() as uow:
        uow.session.add(
            SecretSetting(
                plugin_key="weather",
                name="api_key",
                ciphertext=box.encrypt(SECRET, context="plugins.setting:weather:api_key"),
                updated_at=utc_now(),
            )
        )
    return Network(pl.database, box, transport=httpx.MockTransport(answer), resolver=resolve), seen


GRANT = {"hosts": MANIFEST.network_hosts}


async def call(network: Network, url: str, **kwargs: Any) -> dict[str, Any]:
    return await network("weather", MANIFEST, GRANT, {"method": "GET", "url": url, **kwargs}, None)


async def test_listed_hosts_only_and_secrets_added_by_portalab(
    network: tuple[Network, list[httpx.Request]], caplog: pytest.LogCaptureFixture
) -> None:
    net, seen = network
    caplog.set_level(logging.DEBUG)
    answer = await call(net, "https://api.example.org/forecast", params={"city": "Paris"})
    assert answer["status"] == 200
    sent = seen[-1]
    assert (
        sent.url.host == "93.184.215.14" and sent.headers["host"] == "api.example.org"
    )  # the address resolved
    assert sent.headers["x-api-key"] == SECRET and sent.url.params["city"] == "Paris"
    assert "set-cookie" not in answer["headers"]
    assert SECRET.encode() not in answer["body"] and b"[secret]" in answer["body"]  # echoed back: masked
    for refused, code in (
        ("https://other.example.org/", "denied_host"),
        ("https://api.example.org:8443/", "denied_host"),
        ("http://api.example.org/", "denied_host"),
        ("https://user:pw@api.example.org/", "invalid"),
        ("https://rebind.example.org/", "private_address"),
    ):
        with pytest.raises(Denied) as error:
            await call(net, refused)
        assert error.value.code == code, refused
    assert (await call(net, "https://lan.example.org/"))["status"] == 200  # listed as private
    redirected = await call(net, "https://api.example.org/redirect")
    assert redirected["status"] == 302 and len(seen) == 3  # not followed
    other = await call(net, "https://lan.example.org/")
    assert "x-api-key" not in seen[-1].headers  # a secret goes to its own host only
    assert SECRET not in str(other) and SECRET not in caplog.text
