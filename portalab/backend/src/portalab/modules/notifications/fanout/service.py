"""Fan-out (T011, T014, T017; R3, R4, R7, R8): for each recipient of a communication —

1. **re-authorize** against its ``required_permission`` (lost ⇒ ``suppressed(permission_lost)``), and drop
   expired communications (``valid_until``);
2. resolve the channels (policy ∩ preference, mandatory channels, critical portal bypass);
3. render the ICU template **in the recipient's language** (026) — parameters are values, the text is
   plain (no markup);
4. portal: coalesce repeats of the same ``(category, subject)`` within the window into one item with a
   count (critical never coalesced), then a content-free live ping ``notification.created``;
5. e-mail: an outbox row (or the digest when the user chose one); without an address ⇒
   ``suppressed(no_address)``. Each channel is independent: one failing never blocks the other.
"""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.i18n import RENDERER, RESOLVER, LocaleContext
from portalab.capabilities.identity_directory import CONTACT
from portalab.capabilities.notifications import CategoryRegistry
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.jobs.queue import enqueue
from portalab.core.live import publish_live
from portalab.core.time import Clock, utc_now
from portalab.modules.notifications.models import Communication, Delivery, EmailOutbox, Notification
from portalab.modules.notifications.observability import log, metrics
from portalab.modules.notifications.preferences.resolver import decide
from portalab.modules.notifications.settings import DIGEST, PREFERENCES, NotificationsConfig

RANK = {"low": 0, "normal": 1, "high": 2, "critical": 3}
EMAIL_JOB = "notifications.send_email"
LIVE_TOPIC = "notification.created"


def address_hash(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode()).hexdigest()


class FanOut:
    def __init__(
        self,
        database: Database,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        categories: CategoryRegistry,
        config: Callable[[], NotificationsConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.categories = categories
        self.config = config
        self.clock = clock

    def _provider(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def user_setting(self, key: str, user: UUID, default: Any) -> Any:
        reader = self._provider(CONFIG)
        if reader is None:
            return default
        try:
            return (await reader.get(key, user_id=user)).value
        except Exception:
            return default

    async def locale(self, user: UUID) -> LocaleContext:
        resolver = self._provider(RESOLVER)
        if resolver is None:
            return LocaleContext()
        try:
            ctx = await resolver.for_user(user)
            return ctx if isinstance(ctx, LocaleContext) else LocaleContext()
        except Exception:
            return LocaleContext()

    def render(self, template_key: str, params: Mapping[str, Any], ctx: LocaleContext) -> tuple[str, str]:
        namespace, _, key = template_key.partition(":")
        renderer = self._provider(RENDERER)
        if renderer is None:
            return key, ""
        title = str(renderer.t(key, ctx, params, namespace=namespace))
        body = str(renderer.t(f"{key}.body", ctx, params, namespace=namespace))
        return title, "" if body == f"{key}.body" else body

    async def __call__(self, communication: Communication, recipients: Sequence[UUID]) -> int:
        delivered = 0
        for user in recipients:
            try:
                delivered += await self.deliver(communication, user)
            except Exception:
                log.warning(
                    "delivery to one recipient failed", extra={"communication": str(communication.id)}
                )
                metrics.increment("notifications.recipient_failures")
        return delivered

    async def deliver(self, communication: Communication, user: UUID) -> int:
        now = utc_now(self.clock)
        category = self.categories.get(communication.category)
        if category is None:
            return 0
        if communication.required_permission and not await self._allowed(
            user, communication.required_permission
        ):
            await self._record(communication, user, "portal", "suppressed", "permission_lost")
            metrics.increment("notifications.suppressed.permission_lost")
            return 0
        if communication.valid_until is not None and now > communication.valid_until:
            await self._record(communication, user, "portal", "suppressed", "expired")
            metrics.increment("notifications.suppressed.expired")
            return 0
        config = self.config()
        preferences = await self.user_setting(PREFERENCES, user, {})
        policy = (config.category_policy or {}).get(communication.category, {})
        channels = decide(
            category, preferences or {}, policy, kind=communication.kind, priority=communication.priority
        )
        ctx = await self.locale(user)
        title, body = self.render(communication.template_key, communication.params, ctx)
        reached = 0
        portal = channels["portal"]
        if portal.enabled:
            notification_id = await self._portal(communication, user, ctx, title, body, now)
            reached = 1
            try:
                async with self.database.unit_of_work() as uow:
                    await publish_live(
                        uow.session,
                        topic=LIVE_TOPIC,
                        payload={
                            "id": str(notification_id),
                            "kind": communication.kind,
                            "priority": communication.priority,
                        },
                        audience_user_id=user,
                        clock=self.clock,
                    )
            except Exception:
                log.warning("live notification ping failed")
        else:
            await self._record(communication, user, "portal", "suppressed", portal.reason)
            metrics.increment(f"notifications.suppressed.{portal.reason or 'preference'}")
        email = channels["email"]
        if not email.enabled:
            await self._record(communication, user, "email", "suppressed", email.reason)
        elif not config.email_enabled:
            await self._record(communication, user, "email", "suppressed", "policy")
        else:
            await self._email(communication, user, title, body, now)
        return reached

    async def _allowed(self, user: UUID, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(Principal(user_id=user), permission)
        except Exception:
            return False

    async def _record(
        self, communication: Communication, user: UUID, channel: str, status: str, reason: str | None = None
    ) -> UUID | None:
        async with self.database.unit_of_work() as uow:
            return await self._delivery(uow.session, communication, user, channel, status, reason)

    async def _delivery(
        self,
        session: AsyncSession,
        communication: Communication,
        user: UUID,
        channel: str,
        status: str,
        reason: str | None = None,
    ) -> UUID | None:
        now = utc_now(self.clock)
        return (
            await session.execute(
                insert(Delivery)
                .values(
                    communication_id=communication.id,
                    user_id=user,
                    channel=channel,
                    status=status,
                    suppress_reason=reason,
                    attempts=0,
                    created_at=now,
                    sent_at=now if status in ("delivered", "sent") else None,
                )
                .on_conflict_do_nothing(constraint="uq_deliveries_recipient_channel")
                .returning(Delivery.id)
            )
        ).scalar_one_or_none()

    async def _portal(
        self, communication: Communication, user: UUID, ctx: LocaleContext, title: str, body: str, now: Any
    ) -> UUID:
        window = timedelta(seconds=max(0, self.config().coalesce_window_seconds))
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if communication.priority != "critical" and communication.subject_ref and window:
                existing = (
                    await session.execute(
                        select(Notification)
                        .where(
                            Notification.user_id == user,
                            Notification.category == communication.category,
                            Notification.subject_ref == communication.subject_ref,
                            Notification.read_at.is_(None),
                            Notification.archived_at.is_(None),
                            Notification.updated_at >= now - window,
                        )
                        .order_by(Notification.updated_at.desc())
                        .limit(1)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.count += 1
                    existing.title, existing.body, existing.updated_at = title, body, now
                    existing.priority_rank = max(existing.priority_rank, RANK[communication.priority])
                    await self._delivery(session, communication, user, "portal", "delivered")
                    metrics.increment("notifications.coalesced")
                    return existing.id
            row = Notification(
                communication_id=communication.id,
                user_id=user,
                language=ctx.language,
                title=title,
                body=body,
                kind=communication.kind,
                category=communication.category,
                priority=communication.priority,
                priority_rank=RANK[communication.priority],
                subject_ref=communication.subject_ref,
                count=1,
                action_url=communication.action_url,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            await self._delivery(session, communication, user, "portal", "delivered")
            metrics.increment("notifications.delivered.portal")
            return row.id

    async def _email(self, communication: Communication, user: UUID, title: str, body: str, now: Any) -> None:
        contact = self._provider(CONTACT)
        address = await contact.email_of(user) if contact is not None else None
        if not address:
            await self._record(communication, user, "email", "suppressed", "no_address")
            metrics.increment("notifications.suppressed.no_address")
            return
        digest = await self.user_setting(DIGEST, user, self.config().digest_default_mode)
        own = communication.email_body or {}  # 027: a newsletter brings its own e-mail
        async with self.database.unit_of_work() as uow:
            delivery = await self._delivery(uow.session, communication, user, "email", "pending")
            if delivery is None or (
                not own and digest in ("daily", "weekly") and communication.priority != "critical"
            ):
                return  # duplicate, or kept for the digest
            link = f"\n\n{communication.action_url}" if communication.action_url else ""
            uow.session.add(
                EmailOutbox(
                    delivery_id=delivery,
                    to_hash=address_hash(address),
                    subject=str(own.get("subject") or title)[:200],
                    body_text=str(own.get("text") or f"{title}\n\n{body}{link}").strip(),
                    body_html=own.get("html") or None,
                    next_attempt_at=now,
                    attempts=0,
                )
            )
            await enqueue(
                uow.session,
                kind=EMAIL_JOB,
                payload={"delivery": str(delivery)},
                dedup_key=f"{EMAIL_JOB}:{delivery}:0",
                clock=self.clock,
            )

    async def mark_read(self, user: UUID, ids: Sequence[UUID] | None) -> int:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            stmt = update(Notification).where(Notification.user_id == user, Notification.read_at.is_(None))
            if ids is not None:
                stmt = stmt.where(Notification.id.in_(ids))
            result = await uow.session.execute(stmt.values(read_at=now))
            return int(getattr(result, "rowcount", 0) or 0)
