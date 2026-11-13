"""What a confined plugin asks Portalab's own services for (spec 030, FR-012-FR-014): notifications, events,
jobs and live channels — always under the plugin's own names, within its grants and limits.
"""

import json
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.jobs.queue import enqueue
from portalab.core.live import publish_live
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.confined.host import Denied
from portalab.modules.plugins.manifest.schema import Manifest

JOB_KIND = "plugins.confined_job"
LIVE_MAX_BYTES = 8 * 1024
LIVE_PER_SECOND = 20
LIVE_BURST = 100
NOTIFY_PER_MINUTE = 120


def _users(raw: Any, limit: int = 500) -> list[UUID]:
    out: list[UUID] = []
    for value in list(raw or [])[:limit]:
        try:
            out.append(UUID(str(value)))
        except ValueError:
            raise Denied("invalid", "a member id is not valid") from None
    return out


class Bucket:
    """At most ``rate`` a second on average, ``burst`` at once."""

    def __init__(self, rate: float, burst: int) -> None:
        self.rate, self.burst = rate, burst
        self._state: dict[str, tuple[float, float]] = {}

    def take(self, key: str) -> bool:
        now = time.monotonic()
        tokens, at = self._state.get(key, (float(self.burst), now))
        tokens = min(float(self.burst), tokens + (now - at) * self.rate)
        if tokens < 1:
            self._state[key] = (tokens, now)
            return False
        self._state[key] = (tokens - 1, now)
        return True


class Services:
    def __init__(
        self,
        database: Database,
        events: EventPublisher | None,
        capabilities: CapabilityRegistry | None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.clock = clock
        self.blocked: Any = (
            None  # (author, recipients) -> recipients without those who blocked the author (012)
        )
        self._live = Bucket(LIVE_PER_SECOND, LIVE_BURST)
        self._notified: dict[str, deque[float]] = defaultdict(deque)

    # --- notifications (010) ----------------------------------------------------------------------------
    async def notify(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> dict[str, Any]:
        users = _users(args.get("users"))
        category = str(args.get("category", ""))
        declared = {str(c.get("name")) for c in manifest.raw.get("ui", {}).get("notification_categories", [])}
        if category not in declared:
            raise Denied("denied", f"the notification category {category[:40]} is not declared")
        now = time.monotonic()
        sent = self._notified[key]
        while sent and now - sent[0] > 60:
            sent.popleft()
        if len(sent) >= NOTIFY_PER_MINUTE:
            raise Denied("rate", "too many notifications")
        sent.append(now)
        providers = self.capabilities.system_providers(NOTIFY) if self.capabilities is not None else []
        if not users or not providers:
            return {"sent": 0}
        title = " ".join(str(args.get("title", "")).split())[:120]
        body = " ".join(str(args.get("body", "")).split())[:300]
        link = str(args.get("link") or "")
        if link and not link.startswith(f"/plugins/{key}/"):
            link = f"/plugins/{key}"
        await providers[0].provider.send(
            CommunicationRequest(
                category=f"plugin:{key}.{category}",
                template_key="plugins:notify.message",
                audience=Users(tuple(users)),
                dedup_key=f"plugin:{key}:{utc_now(self.clock).timestamp():.6f}:{hash(title) & 0xFFFFFF}",
                # issue 398: the plugin's text set apart, never turned into links (a third party wrote it)
                params={"plugin": manifest.name[:60], "title": title, "body": body, "quote": body},
                source="module",
                source_ref=f"plugin:{key}",
                action_url=link or None,
            )
        )
        return {"sent": len(users)}

    # --- events (007) -----------------------------------------------------------------------------------
    async def emit(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> dict[str, Any]:
        name = str(args.get("type", ""))
        produces = set(dict(manifest.capabilities.get("events") or {}).get("produces") or [])
        produces |= set(manifest.raw.get("events", {}).get("produces", []))
        if name not in produces:
            raise Denied("denied", f"the event {name[:40]} is not declared")
        payload = dict(args.get("payload") or {})
        if len(json.dumps(payload, default=str)) > 8 * 1024:
            raise Denied("oversize", "an event payload is at most 8 KiB")
        if self.events is None:
            raise Denied("unavailable", "events are not available")
        subject_id = args.get("subject_id")
        async with self.database.unit_of_work() as uow:
            await self.events.publish(
                uow.session,
                f"plugin.{key}.{name}",
                payload,
                occurred_at=utc_now(self.clock),
                actor=Principal(channel="plugin", acting_for=getattr(acting, "user_id", None)),
                subject=SubjectRef(f"plugin.{key}", str(subject_id)[:120]) if subject_id else None,
                source=f"plugin:{key}",
            )
        return {"id": ""}

    # --- jobs (001) -------------------------------------------------------------------------------------
    async def enqueue_job(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> dict[str, Any]:
        job = str(args.get("job", ""))
        if job not in set(grant.get("names") or []):
            raise Denied("denied", f"the job {job[:40]} is not declared")
        payload = dict(args.get("payload") or {})
        if len(json.dumps(payload, default=str)) > 8 * 1024:
            raise Denied("oversize", "a job payload is at most 8 KiB")
        async with self.database.unit_of_work() as uow:
            result = await enqueue(
                uow.session,
                kind=JOB_KIND,
                payload={"plugin": key, "job": job, "payload": payload},
                clock=self.clock,
            )
        return {"id": str(getattr(result, "id", ""))}

    # --- live channels (001) ----------------------------------------------------------------------------
    async def live(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> dict[str, Any]:
        topic = str(args.get("topic", ""))
        if topic not in set(grant.get("topics") or []):
            raise Denied("denied", f"the live topic {topic[:40]} is not declared")
        payload = dict(args.get("payload") or {})
        if len(json.dumps(payload, default=str)) > LIVE_MAX_BYTES:
            raise Denied("oversize", "a live message is at most 8 KiB")
        if not self._live.take(key):
            raise Denied("rate", "too many live messages")
        users = _users(args.get("users")) if args.get("users") is not None else None
        permission = args.get("permission")
        if permission is not None and not str(permission).startswith(f"plugin:{key}."):
            raise Denied("denied", "a live audience is one of the plugin's own permissions")
        author = args.get("author")
        if users is not None and author and self.blocked is not None:
            users = await self.blocked(UUID(str(author)), users)
        full = f"plugin.{key}.{topic}"
        async with self.database.unit_of_work() as uow:
            if users is None:
                await publish_live(
                    uow.session,
                    topic=full,
                    payload=payload,
                    permission=str(permission or f"plugin:{key}.use"),
                    clock=self.clock,
                )
            else:
                for user in users:
                    await publish_live(
                        uow.session, topic=full, payload=payload, audience_user_id=user, clock=self.clock
                    )
        return {"delivered": len(users) if users is not None else None}
