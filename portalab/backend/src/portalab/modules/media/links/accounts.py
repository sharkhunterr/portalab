"""Service accounts ↔ members (027): the accounts each connected service knows (``service.accounts``), the
link of each one to a portal member, and a *suggestion* when an unlinked account obviously belongs to a member
— same e-mail, else same login or name once accents, case and punctuation are ignored. Suggestions are only
proposals: an administrator applies them (one by one or all at once) and every link they make is verified.

Linking an account also attributes its past activity on that service (sessions recorded as *unlinked*) to the
member; requests are re-attributed by the next synchronisation of the request service.
"""

import asyncio
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update

from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.capabilities.identity_directory import ACCOUNTS as MEMBER_ACCOUNTS
from portalab.capabilities.identity_directory import AccountSummary
from portalab.capabilities.media import ACCOUNTS, ServiceAccount, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import PlaybackSession, UserLink

TIMEOUT_SECONDS = 15


def normalize(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", text)


def suggest(account: ServiceAccount, members: Sequence[AccountSummary]) -> tuple[UUID, str] | None:
    """The member an unlinked account most likely belongs to, and why — or ``None`` when unclear."""
    email = (account.email or "").strip().lower()
    if email:
        hits = [m for m in members if (m.email or "").strip().lower() == email]
        if len(hits) == 1:
            return hits[0].id, "email"
    for value in (account.username, account.display_name):
        key = normalize(value)
        if len(key) < 3:
            continue
        hits = [m for m in members if key in (normalize(m.login), normalize(m.display_name))]
        if len(hits) == 1:
            return hits[0].id, "name"
    return None


@dataclass
class AccountRow:
    external_id: str
    username: str | None
    display_name: str | None
    email: str | None
    linked_user_id: UUID | None = None
    verified: bool = False
    suggestion: tuple[UUID, str] | None = None
    unlinked_sessions: int = 0


@dataclass
class ServiceAccounts:
    service_id: str
    name: str
    connector: str
    available: bool
    accounts: list[AccountRow] = field(default_factory=list)


class AccountMatching:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None):
        self.database = database
        self.capabilities = capabilities
        self.clock = clock

    def _first(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    def _providers(self) -> dict[str, Any]:
        try:
            registrations = self.capabilities.system_providers(ACCOUNTS)
        except Exception:
            return {}
        return {r.instance_ref: r.provider for r in registrations}

    async def members(self) -> list[AccountSummary]:
        directory = self._first(MEMBER_ACCOUNTS)
        return list(await directory.accounts()) if directory is not None else []

    async def overview(self) -> tuple[list[ServiceAccounts], list[AccountSummary]]:
        members = await self.members()
        providers = self._providers()
        directory = self._first(SERVICE_DIRECTORY)
        infos = {s.id: s for s in await directory.services()} if directory is not None else {}
        async with self.database.session() as session:
            links = list((await session.execute(select(UserLink))).scalars())
            unlinked = dict(
                (
                    (str(service), str(external)),
                    int(count),
                )
                for service, external, count in (
                    await session.execute(
                        select(PlaybackSession.service_id, PlaybackSession.external_user_id, func.count())
                        .where(
                            PlaybackSession.user_id.is_(None), PlaybackSession.external_user_id.is_not(None)
                        )
                        .group_by(PlaybackSession.service_id, PlaybackSession.external_user_id)
                    )
                ).all()
            )
        linked_by_member = {(str(link.service_id), link.user_id) for link in links}
        out: list[ServiceAccounts] = []
        for service_id, provider in providers.items():
            info = infos.get(service_id)
            block = ServiceAccounts(
                service_id,
                info.name if info else service_id,
                info.connector if info else "",
                available=True,
            )
            try:
                accounts: Sequence[ServiceAccount] = list(
                    unwrap(await asyncio.wait_for(provider.list_accounts(), timeout=TIMEOUT_SECONDS))
                )
            except Exception:
                block.available = False
                accounts = []
            by_external = {
                link.external_user_id: link for link in links if str(link.service_id) == service_id
            }
            for account in accounts:
                link = by_external.get(account.external_id)
                row = AccountRow(
                    account.external_id,
                    account.username,
                    account.display_name,
                    account.email,
                    linked_user_id=link.user_id if link else None,
                    verified=bool(link and link.verified),
                    unlinked_sessions=unlinked.get((service_id, account.external_id), 0),
                )
                if link is None:
                    guess = suggest(account, members)
                    # a member already linked to another account of this service is not suggested again
                    if guess is not None and (service_id, guess[0]) not in linked_by_member:
                        row.suggestion = guess
                block.accounts.append(row)
            block.accounts.sort(key=lambda r: (r.linked_user_id is not None, normalize(r.username)))
            out.append(block)
        out.sort(key=lambda b: b.name.lower())
        return out, members

    async def link(self, service_id: UUID, external_user_id: str, user_id: UUID | None) -> int:
        """Point a service account at a member (``None`` unlinks); returns the past sessions attributed."""
        if service_id not in {UUID(k) for k in self._providers()}:
            raise NotFound("This service has no accounts to link.", code="media.not_found")
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await session.execute(
                delete(UserLink).where(
                    UserLink.service_id == service_id, UserLink.external_user_id == external_user_id
                )
            )
            if user_id is None:
                await session.execute(
                    update(PlaybackSession)
                    .where(
                        PlaybackSession.service_id == service_id,
                        PlaybackSession.external_user_id == external_user_id,
                    )
                    .values(user_id=None)
                )
                return 0
            # one account per member and service: the member's previous account here is unlinked
            await session.execute(
                delete(UserLink).where(UserLink.service_id == service_id, UserLink.user_id == user_id)
            )
            session.add(
                UserLink(
                    user_id=user_id,
                    service_id=service_id,
                    external_user_id=external_user_id,
                    verified=True,
                    created_at=utc_now(self.clock),
                )
            )
            result = await session.execute(
                update(PlaybackSession)
                .where(
                    PlaybackSession.service_id == service_id,
                    PlaybackSession.external_user_id == external_user_id,
                    PlaybackSession.user_id.is_(None),
                )
                .values(user_id=user_id)
            )
            return int(getattr(result, "rowcount", 0) or 0)

    async def apply_suggestions(self, service_id: UUID | None = None) -> int:
        blocks, _ = await self.overview()
        made = 0
        for block in blocks:
            if service_id is not None and block.service_id != str(service_id):
                continue
            taken: set[UUID] = set()
            for row in block.accounts:
                if row.linked_user_id is None and row.suggestion and row.suggestion[0] not in taken:
                    taken.add(row.suggestion[0])
                    await self.link(UUID(block.service_id), row.external_id, row.suggestion[0])
                    made += 1
        return made
