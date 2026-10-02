"""005 T008 — ConnectorHttpClient: size cap, same-host redirects, retries, correlation id, redaction."""

import httpx
import pytest

from portalab.capabilities.connector_http import (
    ConnectorHttpClient,
    ConnectorHttpError,
    RedirectRefused,
    ResponseTooLarge,
)
from portalab.core.logging import correlation_scope

SECRET = "s3cr3t-value-for-tests"


def client(handler: httpx.MockTransport, **kwargs: object) -> ConnectorHttpClient:
    return ConnectorHttpClient(
        "http://media.lan:8080/api",
        transport=handler,
        backoff_seconds=0,
        secrets={"token": SECRET},
        **kwargs,  # type: ignore[arg-type]
    )


async def test_get_json_and_correlation_id() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    with correlation_scope("corr-123"):
        response = await client(httpx.MockTransport(handle)).get("items")
    assert response.json() == {"ok": True}
    assert str(seen[0].url) == "http://media.lan:8080/api/items"
    assert seen[0].headers["X-Correlation-Id"] == "corr-123"


async def test_response_size_is_capped() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 2048))
    with pytest.raises(ResponseTooLarge):
        await client(transport, max_response_bytes=1024).get("big")


async def test_redirect_to_other_host_refused() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "media.lan":
            return httpx.Response(302, headers={"location": "http://evil.example/steal"})
        return httpx.Response(200)

    with pytest.raises(RedirectRefused):
        await client(httpx.MockTransport(handle)).get("items")


async def test_same_host_redirect_followed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/old"):
            return httpx.Response(301, headers={"location": "/api/new"})
        return httpx.Response(200, json={"moved": True})

    assert (await client(httpx.MockTransport(handle)).get("old")).json() == {"moved": True}


async def test_idempotent_requests_retry_then_succeed() -> None:
    calls = {"n": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={})

    await client(httpx.MockTransport(handle), retries=2).get("items")
    assert calls["n"] == 3


async def test_post_is_not_retried_and_errors_are_redacted() -> None:
    calls = {"n": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError(f"failed with token={SECRET}", request=request)

    with pytest.raises(ConnectorHttpError) as error:
        await client(httpx.MockTransport(handle), retries=3).post("items")
    assert calls["n"] == 1 and SECRET not in str(error.value)


async def test_server_errors_retried_for_get() -> None:
    codes = iter([503, 200])
    transport = httpx.MockTransport(lambda request: httpx.Response(next(codes)))
    assert (await client(transport, retries=1).get("x")).status_code == 200


def test_base_url_must_be_absolute() -> None:
    with pytest.raises(ConnectorHttpError):
        ConnectorHttpClient("media.lan/api")
