"""E-mail channel (T026, T027; R10): an ``EmailTransport`` port with an SMTP adapter (``aiosmtplib``),
an outbox processed by the ``notifications.send_email`` job with exponential backoff and an attempt cap,
an optional digest, and the e-mail ``VerificationChannel`` for identity (002).

The clear address is only read from identity at send time (never stored here, never logged — the outbox
keeps a hash); bodies are removed once sent; errors are recorded as error classes, never messages."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from email.headerregistry import Address
from email.message import EmailMessage as MimeMessage
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.i18n import RENDERER, RESOLVER, TIME, LocaleContext
from portalab.capabilities.identity_directory import CONTACT
from portalab.capabilities.notifications import EmailMessage, EmailTransport
from portalab.capabilities.notifications.layout import button, code, dress, items_list, paragraphs, site_brand
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.queue import enqueue
from portalab.core.time import Clock, utc_now
from portalab.modules.notifications.channels.look import brand, words
from portalab.modules.notifications.models import Communication, Delivery, DigestState, EmailOutbox
from portalab.modules.notifications.observability import log, metrics
from portalab.modules.notifications.settings import DIGEST, SMTP_PASSWORD, NotificationsConfig

EMAIL_JOB = "notifications.send_email"
BASE_BACKOFF = 30
MAX_BACKOFF = 3600


async def _unnamed() -> str:
    return ""


def sender(name: str, address: str) -> str | Address:
    """#339: ``Name <address>`` — the bare address when there is no name, or an address it cannot carry."""
    name = " ".join(name.split())[:100]
    if not name:
        return address
    try:
        return Address(display_name=name, addr_spec=address)
    except (ValueError, IndexError):
        return address


class SmtpTransport:
    def __init__(
        self,
        config: Callable[[], NotificationsConfig],
        password: Callable[[], Awaitable[str]],
        name: Callable[[], Awaitable[str]] = _unnamed,
    ) -> None:
        self.config = config
        self.password = password
        self.name = name

    async def send(self, message: EmailMessage) -> None:
        import aiosmtplib

        config = self.config()
        mime = MimeMessage()
        mime["From"] = sender(await self.name(), config.email_from)
        mime["To"] = message.to
        mime["Subject"] = message.subject.replace("\n", " ")[:200]
        mime.set_content(message.text)
        if message.html:
            mime.add_alternative(message.html, subtype="html")
        password = await self.password()
        await aiosmtplib.send(
            mime,
            hostname=config.smtp_host,
            port=config.smtp_port,
            use_tls=config.smtp_tls and config.smtp_port == 465,
            start_tls=config.smtp_tls and config.smtp_port != 465,
            username=config.smtp_username or None,
            password=password or None,
            timeout=15,
        )


def backoff(attempt: int) -> int:
    return int(min(BASE_BACKOFF * 2 ** max(attempt - 1, 0), MAX_BACKOFF))


class EmailChannel:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        config: Callable[[], NotificationsConfig],
        *,
        transport: EmailTransport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.config = config
        self.clock = clock
        self.transport: EmailTransport = transport or SmtpTransport(
            config, self.smtp_password, self.sender_name
        )

    def _provider(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def smtp_password(self) -> str:
        reader = self._provider(CONFIG)
        if reader is None:
            return ""
        try:
            return str((await reader.get(SMTP_PASSWORD)).value or "")
        except Exception:
            return ""

    async def sender_name(self) -> str:
        """#339: the name the e-mails come from — the one set, else the site's own name."""
        return self.config().email_from_name.strip() or (await site_brand(self._provider, "", "en")).name

    async def address(self, user: UUID) -> str | None:
        contact = self._provider(CONTACT)
        return await contact.email_of(user) if contact is not None else None

    async def run(self, payload: dict[str, Any]) -> None:
        """Job handler: send one outbox message (retry with backoff, then ``failed``)."""
        delivery_id = UUID(str(payload["delivery"]))
        async with self.database.session() as session:
            outbox = await session.get(EmailOutbox, delivery_id)
            delivery = await session.get(Delivery, delivery_id)
        if outbox is None or delivery is None or delivery.status != "pending":
            return  # already handled (sent, failed or suppressed)
        address = await self.address(delivery.user_id)
        now = utc_now(self.clock)
        if not address:
            await self._finish(delivery_id, "suppressed", reason="no_address")
            return
        try:
            await asyncio.wait_for(
                self.transport.send(
                    EmailMessage(address, outbox.subject, outbox.body_text, outbox.body_html)
                ),
                timeout=30,
            )
        except Exception as exc:
            await self._failed_attempt(delivery_id, type(exc).__name__, now)
            return
        await self._finish(delivery_id, "sent")
        metrics.increment("notifications.delivered.email")

    async def _finish(
        self, delivery_id: UUID, status: str, *, reason: str | None = None, error: str | None = None
    ) -> None:
        async with self.database.unit_of_work() as uow:
            delivery = await uow.session.get(Delivery, delivery_id, with_for_update=True)
            if delivery is None:
                return
            delivery.status, delivery.suppress_reason = status, reason
            delivery.last_error = error
            if status == "sent":
                delivery.sent_at = utc_now(self.clock)
            await uow.session.execute(
                delete(EmailOutbox).where(EmailOutbox.delivery_id == delivery_id)
            )  # minimization

    async def _failed_attempt(self, delivery_id: UUID, error: str, now: datetime) -> None:
        metrics.increment("notifications.email.errors")
        async with self.database.unit_of_work() as uow:
            outbox = await uow.session.get(EmailOutbox, delivery_id, with_for_update=True)
            delivery = await uow.session.get(Delivery, delivery_id, with_for_update=True)
            if outbox is None or delivery is None:
                return
            outbox.attempts += 1
            delivery.attempts, delivery.last_error = outbox.attempts, error[:200]
            if outbox.attempts >= max(1, self.config().email_max_attempts):
                delivery.status = "failed"
                await uow.session.delete(outbox)
                await self.events.publish(
                    uow.session,
                    "notification.delivery_failed",
                    {"channel": "email", "minute": now.strftime("%Y-%m-%dT%H:%M")},
                    occurred_at=now,
                    source="notifications",
                    dedup_key=f"notification.delivery_failed:email:{now.strftime('%Y-%m-%dT%H:%M')}",
                )
                log.warning("e-mail delivery failed for good", extra={"error": error})
                return
            outbox.next_attempt_at = now + timedelta(seconds=backoff(outbox.attempts))
            await enqueue(
                uow.session,
                kind=EMAIL_JOB,
                payload={"delivery": str(delivery_id)},
                dedup_key=f"{EMAIL_JOB}:{delivery_id}:{outbox.attempts}",
                run_at=outbox.next_attempt_at,
                clock=self.clock,
            )

    async def digest(self) -> int:
        """Daily/weekly digests: pending e-mail deliveries kept for the digest become one message."""
        now = utc_now(self.clock)
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Delivery, Communication)
                    .join(Communication, Communication.id == Delivery.communication_id)
                    .where(Delivery.channel == "email", Delivery.status == "pending")
                    .where(~Delivery.id.in_(select(EmailOutbox.delivery_id)))
                )
            ).all()
        by_user: dict[UUID, list[tuple[Delivery, Communication]]] = defaultdict(list)
        for delivery, communication in rows:
            by_user[delivery.user_id].append((delivery, communication))
        sent = 0
        for user, items in by_user.items():
            reader = self._provider(CONFIG)
            mode = "off"
            if reader is not None:
                try:
                    mode = str((await reader.get(DIGEST, user_id=user)).value)
                except Exception:
                    mode = "off"
            period = timedelta(days=7 if mode == "weekly" else 1)
            async with self.database.session() as session:
                state = await session.get(DigestState, user)
            if state is not None and now - state.last_digest_at < period:
                continue
            address = await self.address(user)
            ids = [delivery.id for delivery, _ in items]
            if not address:
                for delivery_id in ids:
                    await self._finish(delivery_id, "suppressed", reason="no_address")
                continue
            ctx = await self._locale(user)
            lines = [self._title(communication, ctx) for _, communication in items]
            subject = self._title_key("notifications:digest.subject", ctx, len(lines))
            site = await brand(self._provider, self.config().portal_url, ctx.language)
            center = site.link("/notifications")
            try:
                await self.transport.send(
                    EmailMessage(
                        address,
                        subject,
                        "\n".join(f"• {line}" for line in lines),
                        dress(  # #320: the digest in Portalab's look
                            site,
                            title=subject,
                            body_html=items_list(lines)
                            + (
                                button(
                                    words(
                                        self._provider, "notifications:email.open", ctx, {"site": site.name}
                                    ),
                                    center,
                                )
                                if center.startswith("http")
                                else ""
                            ),
                            kicker=words(self._provider, "notifications:email.digest", ctx),
                            note=words(self._provider, "notifications:email.note", ctx),
                            language=ctx.language,
                        ),
                    )
                )
            except Exception as exc:
                log.warning("digest not sent", extra={"error": type(exc).__name__})
                continue
            async with self.database.unit_of_work() as uow:
                for delivery_id in ids:
                    delivery = await uow.session.get(Delivery, delivery_id)
                    if delivery is not None:
                        delivery.status, delivery.sent_at = "sent", now
                existing = await uow.session.get(DigestState, user)
                if existing is None:
                    uow.session.add(DigestState(user_id=user, last_digest_at=now))
                else:
                    existing.last_digest_at = now
            sent += 1
        return sent

    async def _locale(self, user: UUID) -> LocaleContext:
        resolver = self._provider(RESOLVER)
        try:
            return await resolver.for_user(user) if resolver is not None else LocaleContext()
        except Exception:
            return LocaleContext()

    def _title(self, communication: Communication, ctx: LocaleContext) -> str:
        namespace, _, key = communication.template_key.partition(":")
        renderer = self._provider(RENDERER)
        return str(renderer.t(key, ctx, communication.params, namespace=namespace)) if renderer else key

    def _title_key(self, template: str, ctx: LocaleContext, count: int) -> str:
        namespace, _, key = template.partition(":")
        renderer = self._provider(RENDERER)
        return str(renderer.t(key, ctx, {"count": count}, namespace=namespace)) if renderer else key


class EmailVerificationChannel:
    """Identity's ``VerificationChannel`` over e-mail (002): when e-mail is enabled and the account has an
    address; otherwise nothing is sent and the Admin hands the token over (baseline)."""

    def __init__(self, channel: EmailChannel) -> None:
        self.channel = channel

    async def deliver(self, user_id: UUID, token: str, expires_at: datetime) -> None:
        if not self.channel.config().email_enabled:
            return
        address = await self.channel.address(user_id)
        if not address:
            return
        ctx = await self.channel._locale(user_id)
        renderer = self.channel._provider(RENDERER)
        time = self.channel._provider(TIME)
        try:  # issue 398: the moment in the reader's language and time zone
            expires = str(time.render_instant(expires_at, ctx, "medium")) if time else expires_at.isoformat()
        except Exception:
            expires = expires_at.isoformat()
        subject = (
            str(renderer.t("verification.subject", ctx, {}, namespace="notifications"))
            if renderer
            else "Portalab"
        )
        text = (
            str(
                renderer.t(
                    "verification.body",
                    ctx,
                    {"token": token, "expires": expires},
                    namespace="notifications",
                )
            )
            if renderer
            else token
        )
        site = await brand(self.channel._provider, self.channel.config().portal_url, ctx.language)
        # issue 398: one click to the confirmation page, the code in the address's fragment (never sent to
        # the server, so never in its logs nor in a Referer)
        page = site.link(f"/verify#token={token}")
        action = (
            button(words(self.channel._provider, "notifications:verification.action", ctx), page)
            if page.startswith("http")
            else ""
        )
        html = dress(  # #320: in Portalab's look, the code standing out
            site,
            title=subject,
            body_html=paragraphs(text.replace(token, "").strip()) + code(token) + action,
            kicker=words(self.channel._provider, "notifications:email.account", ctx),
            note=words(self.channel._provider, "notifications:email.verificationNote", ctx),
            language=ctx.language,
        )
        try:
            await self.channel.transport.send(EmailMessage(address, subject, text, html))
        except Exception as exc:
            log.warning("verification e-mail not sent", extra={"error": type(exc).__name__})
