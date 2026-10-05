"""ServiceManager (T011, T031): configured services, their state machine and capability provision.

States (spec "Connector State Model"): ``configured`` → ``enabled`` (after a passing compatibility and
connection check) ⇄ ``error | unavailable | maintenance`` (conditions, system) → ``disabled`` (admin,
re-enable possible) — and any state → ``disconnected`` (admin; final). Capabilities are provided only while
the service is enabled; conditions short-circuit calls to last-known data; disabling or disconnecting
withdraws them and **never** deletes historized data (a purge is the separate 021 action). Sync state is
kept apart (``sync_state``), so "syncing" is a sync status, not a persisted service state.
Credentials are write-only: encrypted per field, never returned, and erased on disconnect.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.connector_sdk import Connector, ConnectorRegistry, ServiceHandle, TestResult
from portalab.capabilities.isolation import IsolationPolicy, ProviderGuard
from portalab.capabilities.registry import CapabilityError, CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.ids import new_id
from portalab.core.logging import redact_text
from portalab.core.secrets import SecretBox, SecretDecryptError
from portalab.core.time import Clock, utc_now
from portalab.modules.connectors.breaker.breaker import BreakerBoard, BreakerState
from portalab.modules.connectors.http.client import client_for
from portalab.modules.connectors.models import (
    CompatibilityCheck,
    Service,
    ServiceCapability,
    SyncState,
)
from portalab.modules.connectors.observability import log, metric_part, metrics
from portalab.modules.connectors.services.common import (
    ConnectionTestFailed,
    ConnectorIncompatible,
    ConnectorNotFound,
    InvalidServiceConfig,
    InvalidTransition,
    ServiceNotFound,
    audit,
    publish,
    service_ref,
)
from portalab.modules.connectors.services.compatibility import Compatibility, CompatibilityChecker
from portalab.modules.connectors.services.providers import guarded_provider
from portalab.modules.connectors.services.tester import run_connection_test
from portalab.modules.connectors.settings import ConnectorsConfig

SYSTEM = Principal(channel="system")
ACTIVE = frozenset({"enabled", "error", "unavailable", "maintenance"})  # capabilities registered
CONDITIONS = frozenset({"error", "unavailable", "maintenance"})
TRANSITIONS: dict[str, frozenset[str]] = {
    "configured": frozenset({"enabled", "disconnected"}),
    "enabled": frozenset({"error", "unavailable", "maintenance", "disabled", "disconnected"}),
    "error": frozenset({"enabled", "unavailable", "maintenance", "disabled", "disconnected"}),
    "unavailable": frozenset({"enabled", "error", "maintenance", "disabled", "disconnected"}),
    "maintenance": frozenset({"enabled", "error", "unavailable", "disabled", "disconnected"}),
    "disabled": frozenset({"enabled", "disconnected"}),
    "disconnected": frozenset(),
}


def owner_of(service_id: UUID | str) -> str:
    return f"service:{service_id}"


def secret_context(service_id: UUID | str, name: str) -> str:
    return f"connectors.service:{service_id}:{name}"


@dataclass(frozen=True, slots=True)
class ServiceView:
    id: UUID
    connector_key: str
    name: str
    config: Mapping[str, Any]
    secrets_set: list[str]
    state: str
    state_reason: str | None
    state_changed_at: datetime
    sync_interval_seconds: int | None
    capabilities: list[dict[str, Any]]
    sync: dict[str, Any]
    health: BreakerState
    historical: bool
    stale: bool
    created_at: datetime
    updated_at: datetime
    public_url: str | None = None  # 027: where members open it

    @property
    def display_state(self) -> str:
        return "syncing" if self.state == "enabled" and self.sync.get("status") == "running" else self.state


@dataclass
class ManagerHooks:
    """Test seams: an HTTP transport for the connector client and the isolation policy of providers."""

    http_transport: Any = None
    isolation: IsolationPolicy = field(default_factory=IsolationPolicy)


class ServiceManager:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit_sink: AuditSink,
        capabilities: CapabilityRegistry,
        connectors: ConnectorRegistry,
        secret_box: SecretBox,
        *,
        config: ConnectorsConfig | None = None,
        clock: Clock | None = None,
        breakers: BreakerBoard | None = None,
        checker: CompatibilityChecker | None = None,
        hooks: ManagerHooks | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit_sink
        self.capabilities = capabilities
        self.connectors = connectors
        self.box = secret_box
        self.config = config or ConnectorsConfig()
        self.clock = clock
        self.breakers = breakers or BreakerBoard(
            threshold=self.config.circuit_failure_threshold,
            open_seconds=self.config.circuit_open_seconds,
            clock=clock,
        )
        self.breakers.listener_factory = self._breaker_listener
        self.checker = checker or CompatibilityChecker(connectors, capabilities)
        self.hooks = hooks or ManagerHooks()
        self._states: dict[str, str] = {}  # service id → persisted state as known by this process

    # --- reads ------------------------------------------------------------------------------------------
    def connector(self, key: str) -> Connector:
        connector = self.connectors.get(key)
        if connector is None:
            raise ConnectorNotFound("This connector is not installed.")
        return connector

    def catalog(self) -> list[dict[str, Any]]:
        items = []
        for connector in self.connectors.all():
            compatibility = self.checker.check(connector)
            items.append(
                {
                    "key": connector.key,
                    "name": connector.name,
                    "description": str(getattr(connector, "description", "")),
                    "icon": str(getattr(connector, "icon", "server")),
                    "category": str(getattr(connector, "category", "other")),
                    "version": connector.manifest.version,
                    "provides": [binding.spec.name for binding in connector.provides],
                    # 027: what « sync now » runs; the others are read continuously (history, metadata…)
                    "syncable": [binding.spec.name for binding in connector.provides if binding.syncable],
                    "config_schema": connector.config_schema.model_json_schema(),
                    "secret_fields": sorted(connector.secret_fields),
                    "compatibility": {"result": compatibility.result, "reasons": compatibility.reasons},
                }
            )
        return items

    async def _row(self, session: AsyncSession, service_id: UUID, *, lock: bool = False) -> Service:
        statement = select(Service).where(Service.id == service_id)
        if lock:
            statement = statement.with_for_update()
        row = (await session.execute(statement)).scalar_one_or_none()
        if row is None:
            raise ServiceNotFound("No such service.")
        return row

    async def _view(self, session: AsyncSession, row: Service) -> ServiceView:
        caps = (
            await session.execute(
                select(ServiceCapability)
                .where(ServiceCapability.service_id == row.id)
                .order_by(ServiceCapability.capability)
            )
        ).scalars()
        state = await session.get(SyncState, row.id)
        sync = {
            "status": state.status if state else "idle",
            "last_attempt_at": state.last_attempt_at.isoformat() if state and state.last_attempt_at else None,
            "last_success_at": state.last_success_at.isoformat() if state and state.last_success_at else None,
            "next_run_at": state.next_run_at.isoformat() if state and state.next_run_at else None,
            "consecutive_failures": state.consecutive_failures if state else 0,
            "progress": state.progress if state and state.status == "running" else None,
        }
        return ServiceView(
            id=row.id,
            connector_key=row.connector_key,
            name=row.name,
            config=dict(row.config),
            secrets_set=sorted(row.credentials),
            state=row.state,
            state_reason=row.state_reason,
            state_changed_at=row.state_changed_at,
            sync_interval_seconds=row.sync_interval_seconds,
            capabilities=[
                {"capability": c.capability, "enabled": c.enabled, "priority": c.priority} for c in caps
            ],
            sync=sync,
            health=self.breakers.get(str(row.id)).current(),
            historical=row.state == "disconnected",
            stale=row.state != "enabled",
            created_at=row.created_at,
            updated_at=row.updated_at,
            public_url=row.public_url,
        )

    async def list(self) -> list[ServiceView]:
        async with self.database.session() as session:
            rows = (await session.execute(select(Service).order_by(Service.name, Service.id))).scalars().all()
            return [await self._view(session, row) for row in rows]

    async def get(self, service_id: UUID) -> ServiceView:
        async with self.database.session() as session:
            return await self._view(session, await self._row(session, service_id))

    async def connector_key_of(self, service_id: str) -> str | None:
        try:
            parsed = UUID(service_id)
        except ValueError:
            return None
        async with self.database.session() as session:
            key = await session.scalar(select(Service.connector_key).where(Service.id == parsed))
            return str(key) if key is not None else None

    # --- secrets & handles ------------------------------------------------------------------------------
    def _validate_config(self, connector: Connector, config: Mapping[str, Any]) -> dict[str, Any]:
        try:
            model = connector.config_schema.model_validate(dict(config))
        except ValidationError as exc:
            fields = sorted({".".join(str(p) for p in error["loc"]) for error in exc.errors()})
            raise InvalidServiceConfig(
                "The service configuration is invalid.", extensions={"fields": fields}
            ) from exc
        return model.model_dump(mode="json")

    def _encrypt(
        self,
        connector: Connector,
        service_id: UUID,
        current: Mapping[str, str],
        secrets: Mapping[str, str | None],
    ) -> dict[str, str]:
        unknown = set(secrets) - set(connector.secret_fields)
        if unknown:
            raise InvalidServiceConfig("Unknown secret fields.", extensions={"fields": sorted(unknown)})
        merged = dict(current)
        for name, value in secrets.items():
            if value is None or value == "":
                merged.pop(name, None)
            else:
                merged[name] = self.box.encrypt(value, context=secret_context(service_id, name))
        return merged

    def _secrets(self, row: Service) -> dict[str, str]:
        revealed: dict[str, str] = {}
        for name, token in row.credentials.items():
            try:
                revealed[name] = self.box.decrypt(token, context=secret_context(row.id, name)).reveal()
            except SecretDecryptError:
                log.warning("service secret not decryptable", extra={"fields": {"service_id": str(row.id)}})
        return revealed

    def handle(self, row: Service) -> ServiceHandle:
        secrets = self._secrets(row)
        http = client_for(row.config, secrets, self.config, transport=self.hooks.http_transport)
        return ServiceHandle(
            service_id=row.id, name=row.name, config=dict(row.config), secrets=secrets, http=http
        )

    # --- configuration ----------------------------------------------------------------------------------
    async def configure(
        self,
        actor: Principal,
        *,
        connector_key: str,
        name: str,
        config: Mapping[str, Any],
        secrets: Mapping[str, str | None] | None = None,
        sync_interval_seconds: int | None = None,
        session: AsyncSession | None = None,
    ) -> UUID:
        connector = self.connector(connector_key)
        clean = self._validate_config(connector, config)
        service_id = new_id()
        now = utc_now(self.clock)
        credentials = self._encrypt(connector, service_id, {}, secrets or {})
        if session is not None:
            await self._insert(
                session, actor, connector, service_id, name, clean, credentials, sync_interval_seconds, now
            )
            return service_id
        async with self.database.unit_of_work() as uow:
            await self._insert(
                uow.session,
                actor,
                connector,
                service_id,
                name,
                clean,
                credentials,
                sync_interval_seconds,
                now,
            )
        return service_id

    async def _insert(
        self,
        session: AsyncSession,
        actor: Principal,
        connector: Connector,
        service_id: UUID,
        name: str,
        config: dict[str, Any],
        credentials: dict[str, str],
        sync_interval_seconds: int | None,
        now: datetime,
    ) -> None:
        session.add(
            Service(
                id=service_id,
                connector_key=connector.key,
                name=name,
                config=config,
                credentials=credentials,
                state="configured",
                state_seq=0,
                state_changed_at=now,
                sync_interval_seconds=sync_interval_seconds,
                created_by=actor.user_id,
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()
        for binding in connector.provides:
            session.add(
                ServiceCapability(
                    service_id=service_id, capability=binding.spec.name, enabled=True, priority=100
                )
            )
        session.add(SyncState(service_id=service_id, status="idle", consecutive_failures=0))
        await session.flush()
        await audit(
            self.audit,
            session,
            "service.configured",
            actor,
            resource=service_ref(service_id),
            context={"connector": connector.key, "write_only_fields": sorted(credentials)},
        )

    async def update(
        self,
        actor: Principal,
        service_id: UUID,
        *,
        name: str | None = None,
        config: Mapping[str, Any] | None = None,
        secrets: Mapping[str, str | None] | None = None,
        sync_interval_seconds: int | None = None,
        capabilities: Mapping[str, Mapping[str, Any]] | None = None,
        public_url: str | None = None,
    ) -> ServiceView:
        async with self.database.unit_of_work() as uow:
            row = await self._row(uow.session, service_id, lock=True)
            if row.state == "disconnected":
                raise InvalidTransition("A disconnected service cannot be changed.")
            connector = self.connector(row.connector_key)
            changed: list[str] = []
            if name is not None and name != row.name:
                row.name = name
                changed.append("name")
            if config is not None:
                row.config = self._validate_config(connector, {**row.config, **config})
                changed.append("config")
            if secrets:
                row.credentials = self._encrypt(connector, row.id, row.credentials, secrets)
                changed.append("secrets")
            if sync_interval_seconds is not None:
                row.sync_interval_seconds = sync_interval_seconds or None
                changed.append("sync_interval")
            if public_url is not None and (public_url or None) != row.public_url:  # "" clears it
                row.public_url = public_url or None
                changed.append("public_url")
            for capability, values in (capabilities or {}).items():
                cap = (
                    await uow.session.execute(
                        select(ServiceCapability).where(
                            ServiceCapability.service_id == row.id, ServiceCapability.capability == capability
                        )
                    )
                ).scalar_one_or_none()
                if cap is None:
                    raise InvalidServiceConfig("This service does not provide that capability.")
                if "enabled" in values:
                    cap.enabled = bool(values["enabled"])
                if "priority" in values:
                    cap.priority = int(values["priority"])
                changed.append(f"capability:{capability}")
            row.updated_at = utc_now(self.clock)
            await uow.session.flush()
            await audit(
                self.audit,
                uow.session,
                "service.updated",
                actor,
                resource=service_ref(row.id),
                context={"changed": changed},
            )
            state = row.state
        if state in ACTIVE:
            await self._reprovide(service_id)
        return await self.get(service_id)

    # --- tests & compatibility ---------------------------------------------------------------------------
    async def record_compatibility(self, connector: Connector, session: AsyncSession) -> Compatibility:
        result = self.checker.check(connector)
        now = utc_now(self.clock)
        session.add(
            CompatibilityCheck(
                connector_key=connector.key,
                portal_version=self.checker.portal_version,
                result=result.result,
                reasons=list(result.reasons),
                checked_at=now,
            )
        )
        await publish(
            self.events,
            session,
            "connector.compatibility_checked",
            {"connector": connector.key, "result": result.result},
            service_id=None,
            actor=SYSTEM,
            occurred_at=now,
        )
        return result

    # --- state machine ------------------------------------------------------------------------------------
    async def _transition(
        self,
        session: AsyncSession,
        row: Service,
        to: str,
        actor: Principal,
        *,
        reason: str | None = None,
        sensitive: bool = True,
    ) -> str:
        before = row.state
        if to not in TRANSITIONS[before]:
            raise InvalidTransition(f"A {before} service cannot become {to}.")
        now = utc_now(self.clock)
        row.state = to
        row.state_seq += 1
        row.state_reason = redact_text(reason)[:256] if reason else None
        row.state_changed_at = now
        row.updated_at = now
        if to == "enabled" and before in ("configured", "disabled"):
            row.enabled_at = now
        if to == "disabled":
            row.disabled_at = now
        if to == "disconnected":
            row.disconnected_at = now
            row.credentials = {}
        await session.flush()
        if to == "disconnected":
            event_type = "service.disconnected"
        elif to == "enabled" and before in ("configured", "disabled"):
            event_type = "service.connected"
        else:
            event_type = "service.status_changed"
        result = await publish(
            self.events,
            session,
            event_type,
            {
                "service_id": str(row.id),
                "dimension": "connection",
                "connector": row.connector_key,
                "from_state": before,
                "to_state": to,
                "state_seq": row.state_seq,
                "reason": row.state_reason,
            },
            service_id=row.id,
            actor=actor,
            occurred_at=now,
        )
        await audit(
            self.audit,
            session,
            event_type,
            actor,
            resource=service_ref(row.id),
            context={"from": before, "to": to},
            sensitive=sensitive,
            event_id=result.event_id,
        )
        metrics.increment(f"connectors.transitions.{metric_part(to)}")
        return event_type

    async def enable(self, actor: Principal, service_id: UUID) -> ServiceView:
        async with self.database.session() as session:
            row = await self._row(session, service_id)
            if "enabled" not in TRANSITIONS[row.state]:
                raise InvalidTransition(f"A {row.state} service cannot be enabled.")
            connector = self.connector(row.connector_key)
            handle = self.handle(row)
        test = await self._run_test(connector, handle)
        async with self.database.unit_of_work() as uow:
            compatibility = await self.record_compatibility(connector, uow.session)
        if not compatibility.compatible:
            raise ConnectorIncompatible(
                "This connector is not compatible with this portal.",
                extensions={"reasons": compatibility.reasons},
            )
        if not test.ok:
            raise ConnectionTestFailed(
                "The connection test failed; the service stays as it was.",
                extensions={"diagnostics": _diagnostics(test)},
            )
        async with self.database.unit_of_work() as uow:
            row = await self._row(uow.session, service_id, lock=True)
            await self._transition(uow.session, row, "enabled", actor)
        self.breakers.forget(str(service_id))
        await self._reprovide(service_id)
        return await self.get(service_id)

    async def disable(self, actor: Principal, service_id: UUID) -> ServiceView:
        async with self.database.unit_of_work() as uow:
            row = await self._row(uow.session, service_id, lock=True)
            await self._transition(uow.session, row, "disabled", actor)
        self._withdraw(service_id)
        return await self.get(service_id)

    async def disconnect(self, actor: Principal, service_id: UUID) -> ServiceView:
        async with self.database.unit_of_work() as uow:
            row = await self._row(uow.session, service_id, lock=True)
            await self._transition(uow.session, row, "disconnected", actor)
            state = await uow.session.get(SyncState, service_id)
            if state is not None:
                state.next_run_at = None
                state.status = "idle" if state.status == "running" else state.status
        self._withdraw(service_id)
        self.breakers.forget(str(service_id))
        return await self.get(service_id)

    async def set_condition(self, service_id: UUID, to: str, *, reason: str | None = None) -> bool:
        """System transition between ``enabled`` and a condition; ignored if the service is not active."""
        if to not in CONDITIONS | {"enabled"}:
            raise ValueError(f"{to!r} is not a condition")
        async with self.database.unit_of_work() as uow:
            row = await self._row(uow.session, service_id, lock=True)
            if row.state not in ACTIVE or row.state == to:
                return False
            await self._transition(uow.session, row, to, SYSTEM, reason=reason, sensitive=False)
        self._states[str(service_id)] = to
        return True

    def _breaker_listener(self, service_id: str) -> Any:
        async def on_change(before: BreakerState, after: BreakerState) -> None:
            metrics.gauge(
                f"connectors.breaker_open.{metric_part(service_id)}", 1.0 if after == "open" else 0.0
            )
            try:
                if after == "open":
                    await self.set_condition(UUID(service_id), "unavailable", reason="circuit breaker open")
                elif after == "closed":
                    await self.set_condition(UUID(service_id), "enabled", reason="service recovered")
            except Exception:
                log.warning("service condition not recorded", extra={"fields": {"service_id": service_id}})

        return on_change

    # --- capability provision -----------------------------------------------------------------------------
    def declare_specs(self) -> None:
        """Declare the capability contracts of every installed connector, so consumers can resolve them
        (and get an empty list) before any service is enabled."""
        for connector in self.connectors.all():
            for binding in connector.provides:
                try:
                    self.capabilities.spec(binding.spec.name)
                except CapabilityError:
                    self.capabilities.declare(binding.spec)

    def _usable(self, service_id: str) -> bool:
        return self._states.get(service_id) not in ("error", "maintenance")

    def _withdraw(self, service_id: UUID) -> None:
        self.capabilities.unregister(owner_of(service_id))
        self._states.pop(str(service_id), None)

    async def _reprovide(self, service_id: UUID) -> int:
        self._withdraw(service_id)
        async with self.database.session() as session:
            row = await self._row(session, service_id)
            if row.state not in ACTIVE:
                return 0
            caps = {
                c.capability: c
                for c in (
                    await session.execute(
                        select(ServiceCapability).where(ServiceCapability.service_id == row.id)
                    )
                ).scalars()
            }
            return self._provide(row, caps)

    def _provide(self, row: Service, caps: Mapping[str, ServiceCapability]) -> int:
        connector = self.connectors.get(row.connector_key)
        if connector is None:
            log.warning("service connector missing", extra={"fields": {"service_id": str(row.id)}})
            return 0
        key = str(row.id)
        self._states[key] = row.state
        handle = self.handle(row)
        provided = 0
        for binding in connector.provides:
            cap = caps.get(binding.spec.name)
            if cap is None or not cap.enabled:
                continue
            try:
                self.capabilities.spec(binding.spec.name)
            except CapabilityError:
                self.capabilities.declare(binding.spec)
            inner = connector.provider(binding.spec.name, handle)
            if inner is None:
                continue
            proxy = guarded_provider(
                inner,
                binding.spec.protocol,
                capability=binding.spec.name,
                guard=ProviderGuard(
                    source_system=f"{row.connector_key}:{row.id}",
                    policy=self.hooks.isolation,
                    clock=self.clock,
                ),
                breaker=self.breakers.get(key),
                usable=lambda key=key: self._usable(key),  # type: ignore[misc]
            )
            self.capabilities.provide(
                binding.spec.name,
                proxy,
                instance_ref=key,
                priority=cap.priority,
                owner=owner_of(row.id),
                metadata={"service_id": key, "connector": row.connector_key, "name": row.name},
            )
            provided += 1
        return provided

    async def restore(self) -> int:
        """Rebuild this process's provider registrations from the stored states (start-up, refresh)."""
        provided = 0
        self.declare_specs()
        async with self.database.unit_of_work() as uow:
            session = uow.session
            rows = (await session.execute(select(Service))).scalars().all()
            caps_by_service: dict[UUID, dict[str, ServiceCapability]] = {}
            for cap in (await session.execute(select(ServiceCapability))).scalars():
                caps_by_service.setdefault(cap.service_id, {})[cap.capability] = cap
            # a connector upgrade may bring a capability the stored service does not know yet (027: the
            # accounts of a service): it is enabled like the ones present at configuration
            for row in rows:
                connector = self.connectors.get(row.connector_key)
                known = caps_by_service.setdefault(row.id, {})
                for binding in connector.provides if connector is not None else ():
                    if binding.spec.name not in known:
                        added = ServiceCapability(
                            service_id=row.id, capability=binding.spec.name, enabled=True, priority=100
                        )
                        session.add(added)
                        known[binding.spec.name] = added
        for row in rows:
            self._withdraw(row.id)
            if row.state in ACTIVE:
                provided += self._provide(row, caps_by_service.get(row.id, {}))
        return provided

    async def _run_test(self, connector: Connector, handle: ServiceHandle) -> TestResult:
        return await run_connection_test(
            connector, handle, limit_seconds=self.config.http_timeout_seconds * 3
        )


def _diagnostics(test: TestResult) -> dict[str, Any]:
    return {
        "reachable": test.reachable,
        "authenticated": test.authenticated,
        "compatible": test.compatible,
        "detail": redact_text(test.detail),
    }
