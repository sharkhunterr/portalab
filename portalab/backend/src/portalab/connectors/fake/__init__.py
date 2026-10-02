"""``fake`` connector (T012): deterministic, programmable stand-in for an external service.

Used by tests, the conformance kit and demos; never registered in production by default. It provides one
syncable capability (``demo.items``) whose provider lists items, and simulates latency, outages, garbage
payloads, authentication errors and removals. Its "remote" state is an in-process :class:`FakeBackend`
keyed by the configured ``base_url`` so tests can change what the source returns between runs.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from portalab.capabilities.connector_sdk import (
    Candidate,
    CapabilityBinding,
    Manifest,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
    TestResult,
)
from portalab.capabilities.registry import CapabilitySpec
from portalab.capabilities.results import InvalidPayload, ProviderAuthError

CAPABILITY = "demo.items"
Mode = Literal["ok", "slow", "hang", "garbage", "auth_error", "error"]
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


@runtime_checkable
class ItemsProvider(Protocol):
    async def list_items(self) -> list[dict[str, Any]]: ...


SPEC = CapabilitySpec(
    name=CAPABILITY, version="1.0", protocol=ItemsProvider, description="Demo items (fake connector)"
)


class FakeConfig(BaseModel):
    base_url: str = Field(min_length=1, max_length=512)
    library: str = Field(default="main", max_length=64)


@dataclass
class FakeBackend:
    """What the fake external service currently holds."""

    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    removed: set[str] = field(default_factory=set)
    mode: Mode = "ok"
    latency_seconds: float = 0.0
    token: str = "fake-credential"  # noqa: S105 — test double value, not a real credential
    fail_after: int | None = None  # sync raises after yielding this many records
    calls: int = 0
    reachable_targets: set[str] = field(default_factory=set)

    def put(self, external_id: str, at: int = 0, **payload: Any) -> None:
        self.items[external_id] = {"payload": payload, "at": at}
        self.removed.discard(external_id)

    def remove(self, external_id: str) -> None:
        if self.items.pop(external_id, None) is not None:
            self.removed.add(external_id)

    async def answer(self) -> None:
        self.calls += 1
        if self.latency_seconds:
            await asyncio.sleep(self.latency_seconds)
        if self.mode == "hang":
            await asyncio.sleep(3600)
        if self.mode == "auth_error":
            raise ProviderAuthError("credentials rejected by the fake service")
        if self.mode == "error":
            raise ConnectionError("fake service unreachable")


BACKENDS: dict[str, FakeBackend] = {}


def backend(base_url: str) -> FakeBackend:
    return BACKENDS.setdefault(base_url, FakeBackend())


class _Provider:
    def __init__(self, handle: ServiceHandle) -> None:
        self.handle = handle

    async def list_items(self) -> list[dict[str, Any]]:
        remote = backend(str(self.handle.config["base_url"]))
        await remote.answer()
        if remote.mode == "garbage":
            raise InvalidPayload("unexpected payload shape")
        return [{"id": key, **value["payload"]} for key, value in sorted(remote.items.items())]


class FakeConnector:
    key = "fake"
    name = "Fake service"
    manifest = Manifest(version="1.0.0", requires_portal=">=0.1,<2")
    config_schema = FakeConfig
    secret_fields = frozenset({"api_token"})
    provides: Sequence[CapabilityBinding] = (CapabilityBinding(SPEC, syncable=True),)

    def __init__(self, *, key: str = "fake", manifest: Manifest | None = None) -> None:
        self.key = key
        if manifest is not None:
            self.manifest = manifest

    async def test_connection(self, service: ServiceHandle) -> TestResult:
        remote = backend(str(service.config["base_url"]))
        try:
            await remote.answer()
        except ProviderAuthError:
            return TestResult(
                ok=False, reachable=True, authenticated=False, detail="Credentials were rejected."
            )
        except ConnectionError:
            return TestResult(
                ok=False,
                reachable=False,
                authenticated=False,
                detail="Cannot reach the service; check the address and that it is running.",
            )
        if service.secrets.get("api_token") != remote.token:
            return TestResult(
                ok=False, reachable=True, authenticated=False, detail="The API token is missing or wrong."
            )
        return TestResult(ok=True, reachable=True, authenticated=True, detail="Connected.")

    async def discover(self, targets: Sequence[str]) -> list[Candidate]:
        found = []
        for target in targets:
            remote = BACKENDS.get(target)
            if remote is not None and remote.mode == "ok":
                found.append(
                    Candidate(target=target, details={"config": {"base_url": target}, "version": "1.0"})
                )
        return found

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        remote = backend(str(ctx.service.config["base_url"]))
        await remote.answer()
        since = int((cursor or {}).get("at", -1))
        newest = since
        yielded = 0
        for external_id, item in sorted(remote.items.items()):
            if item["at"] <= since:
                continue
            if remote.fail_after is not None and yielded >= remote.fail_after:
                raise ConnectionError("fake service dropped the connection")
            if remote.mode == "garbage":
                yield {"not": "a record"}  # type: ignore[misc]
                continue
            yield SourceRecord(
                source_system=f"fake:{ctx.service.service_id}",
                external_id=external_id,
                kind="item",
                payload=dict(item["payload"]),
                observed_at=_at(item["at"]),
            )
            yielded += 1
            newest = max(newest, item["at"])
        for external_id in sorted(remote.removed):
            yield SourceRecord(
                source_system=f"fake:{ctx.service.service_id}",
                external_id=external_id,
                kind="item",
                payload={},
                observed_at=_at(newest),
                removed=True,
            )
        yield SyncProgress(cursor={"at": newest})

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        return _Provider(service) if capability == CAPABILITY else None

    def actions(self) -> Mapping[str, Callable[[ServiceHandle, Mapping[str, Any]], Any]]:
        async def refresh(service: ServiceHandle, arguments: Mapping[str, Any]) -> dict[str, Any]:
            await backend(str(service.config["base_url"])).answer()
            return {"refreshed": True}

        return {"refresh": refresh}


def _at(minutes: int) -> datetime:
    return EPOCH + timedelta(minutes=max(minutes, 0))
