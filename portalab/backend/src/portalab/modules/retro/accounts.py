"""Each member's own account in a game library (issue 426).

The admin's account links say who is who in RomM; to write *as* a member (their play sessions, saves and
states), the portal needs the member's own authorisation: RomM's device authorisation — the portal asks for
a code, the member approves it in RomM (signed in as themselves), the portal receives a token bound to a
« Portalab » device of theirs, limited to what it does (who they are, play sessions, saves and states). The
token is kept encrypted (the portal's secret box), never shown; the member revokes it here or in RomM.

A household's profiles play with their master's account (their saves labelled with the profile); only the
master authorises. Without an authorisation — or once the library refuses it — the portal writes to the
service's account, as before, and says so.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.capabilities.household import CAPABILITY as HOUSEHOLD
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retro import LinkStart, LinkToken, MemberAccount
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Forbidden, NotFound
from portalab.core.logging import get_logger
from portalab.core.secrets import SecretBox, SecretDecryptError
from portalab.core.time import Clock, utc_now
from portalab.modules.retro.models import LibraryAccount
from portalab.modules.retro.service import TIMEOUT_S, LibraryDenied, RetroService, _call, player_of

log = get_logger("portalab.retro")


class MasterOnly(Forbidden):
    default_code = "retro.account_master_only"
    default_title = "Only the account's holder authorises it"


class NoSuchLibrary(NotFound):
    default_code = "retro.library_not_found"
    default_title = "No such game library"


@dataclass(frozen=True, slots=True)
class AccountState:
    service_id: UUID
    service_name: str | None
    state: str  # none, pending, linked, expired
    username: str | None = None
    expires_at: datetime | None = None
    user_code: str | None = None
    approve_url: str | None = None  # the library's page where the code is approved
    pending_until: datetime | None = None
    interval: int = 5


@dataclass(frozen=True, slots=True)
class Holder:
    """Whose account in the library holds a member's writes (``key``: what the copies remember)."""

    account: MemberAccount
    key: str


def _context(user: UUID, service: UUID, field: str) -> str:
    return f"retro.account:{user}:{service}:{field}"


class AccountService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        retro: RetroService,
        box: SecretBox | None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.retro = retro
        self.box = box
        self.clock = clock

    async def holder_of(self, user: UUID) -> UUID:
        """A profile writes to its master's account; everyone else to their own."""
        providers = self.capabilities.system_providers(HOUSEHOLD)
        if providers:
            try:
                owner = await providers[0].provider.owner_of(user)
            except Exception:
                owner = None
            if owner is not None:
                return UUID(str(owner))
        return user

    def _master(self, viewer: Principal) -> UUID:
        if viewer.profile_of is not None:
            raise MasterOnly("A profile plays with its master's account.")
        return player_of(viewer)

    async def _link_of(self, service: UUID) -> str | None:
        providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
        if not providers:
            return None
        try:
            info = await providers[0].provider.service(str(service))
        except Exception:
            return None
        link = str(getattr(info, "link", None) or "")
        return link.rstrip("/") if link.startswith(("https://", "http://")) else None  # a web address only

    # --- what the member sees ----------------------------------------------------------------------------
    async def states(self, viewer: Principal) -> list[AccountState]:
        holder = await self.holder_of(player_of(viewer))
        libraries = self.retro._libraries()
        async with self.database.session() as session:
            rows = {
                str(row.service_id): row
                for row in await session.scalars(
                    select(LibraryAccount).where(LibraryAccount.user_id == holder)
                )
            }
        return [await self._state(UUID(ref), name, rows.get(ref)) for ref, (_, name) in libraries.items()]

    async def _state(self, service: UUID, name: str | None, row: LibraryAccount | None) -> AccountState:
        now = utc_now(self.clock)
        if row is None or (row.state == "pending" and (row.pending_until or now) <= now):
            return AccountState(service, name, "none")
        expired = row.state == "expired" or (row.expires_at is not None and row.expires_at <= now)
        base = await self._link_of(service) if row.state == "pending" else None
        return AccountState(
            service_id=service,
            service_name=name,
            state="expired" if row.state == "linked" and expired else row.state,
            username=row.username,
            expires_at=row.expires_at,
            user_code=row.user_code if row.state == "pending" else None,
            approve_url=f"{base}{row.path}" if base and row.path and row.state == "pending" else None,
            pending_until=row.pending_until if row.state == "pending" else None,
            interval=row.interval,
        )

    async def begin(self, viewer: Principal, service: UUID) -> AccountState:
        """Ask the library for the member's authorisation: a code they approve there."""
        holder = self._master(viewer)
        library, name = self._library(service)
        box = self._box()
        started: LinkStart = await _call(library.begin_link(f"portalab-{holder.hex}", "Portalab"))
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(LibraryAccount, (holder, service), with_for_update=True)
            if row is None:
                row = LibraryAccount(user_id=holder, service_id=service, scopes=[], created_at=now)
                uow.session.add(row)
            if row.state != "linked":  # a linked account keeps writing while a new authorisation waits
                row.state = "pending"
            row.device_code = box.encrypt(started.device_code, context=_context(holder, service, "device"))
            row.user_code = started.user_code[:32]
            row.path = started.path[:512]
            row.pending_until = now + timedelta(seconds=max(30, started.expires_in))
            row.interval = started.interval
            row.updated_at = now
        base = await self._link_of(service)
        return AccountState(
            service_id=service,
            service_name=name,
            state="pending",
            user_code=started.user_code[:32],
            approve_url=f"{base}{started.path}" if base else None,
            pending_until=now + timedelta(seconds=max(30, started.expires_in)),
            interval=started.interval,
        )

    async def check(self, viewer: Principal, service: UUID) -> AccountState:
        """Whether the member approved it yet (the page asks every ``interval`` seconds while it waits)."""
        holder = self._master(viewer)
        library, name = self._library(service)
        box = self._box()
        now = utc_now(self.clock)
        async with self.database.session() as session:
            row = await session.get(LibraryAccount, (holder, service))
        if row is None or row.device_code is None or row.pending_until is None:
            return await self._state(service, name, row)
        if row.pending_until <= now:
            await self._drop_request(holder, service)
            return await self._state(service, name, await self._row(holder, service))
        try:
            code = box.decrypt(row.device_code, context=_context(holder, service, "device")).reveal()
            found: LinkToken | None = await _call(library.finish_link(code))
        except (LibraryDenied, SecretDecryptError):
            await self._drop_request(holder, service)  # refused (or expired) in the library
            return await self._state(service, name, await self._row(holder, service))
        if found is None:
            return await self._state(service, name, row)  # still waiting
        async with self.database.unit_of_work() as uow:
            linked = await uow.session.get(LibraryAccount, (holder, service), with_for_update=True)
            if linked is None:
                linked = LibraryAccount(user_id=holder, service_id=service, created_at=now)
                uow.session.add(linked)
            linked.state = "linked"
            linked.token = box.encrypt(found.token, context=_context(holder, service, "token"))
            linked.device_id = (found.device_id or "")[:64] or None
            linked.username = found.username
            linked.scopes = list(found.scopes)[:32]
            linked.expires_at = found.expires_at
            linked.device_code = linked.user_code = linked.path = None
            linked.pending_until = None
            linked.updated_at = now
        return await self._state(service, name, await self._row(holder, service))

    async def unlink(self, viewer: Principal, service: UUID) -> None:
        """The member's authorisation revoked in the library too (when it still answers)."""
        holder = self._master(viewer)
        found = await self.account_for(holder, service, live_only=False)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                delete(LibraryAccount).where(
                    LibraryAccount.user_id == holder, LibraryAccount.service_id == service
                )
            )
        library = self.retro._libraries().get(str(service))
        if found is not None and library is not None:
            try:
                await asyncio.wait_for(library[0].end_link(found.account), timeout=TIMEOUT_S)
            except Exception:
                log.warning("retro account not revoked in the library", extra={"service": str(service)})

    # --- what the portal writes with ---------------------------------------------------------------------
    async def account_for(self, user: UUID, service: UUID, *, live_only: bool = True) -> Holder | None:
        """The member's (or their master's) own account in this library, while it holds."""
        if self.box is None:
            return None
        holder = await self.holder_of(user)
        row = await self._row(holder, service)
        if row is None or row.token is None:
            return None
        if live_only and (
            row.state == "expired" or (row.expires_at is not None and row.expires_at <= utc_now(self.clock))
        ):
            return None
        try:
            token = self.box.decrypt(row.token, context=_context(holder, service, "token")).reveal()
        except SecretDecryptError:
            return None
        return Holder(account=MemberAccount(token=token, device_id=row.device_id), key=holder.hex)

    async def refused(self, user: UUID, service: UUID) -> None:
        """The library refused the member's token (revoked there, expired): writes go back to the service's
        account, and the member is asked to authorise again."""
        holder = await self.holder_of(user)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(LibraryAccount, (holder, service), with_for_update=True)
            if row is not None and row.state == "linked":
                row.state = "expired"
                row.updated_at = utc_now(self.clock)

    # --- helpers ------------------------------------------------------------------------------------------
    def _library(self, service: UUID) -> tuple[Any, str | None]:
        found = self.retro._libraries().get(str(service))
        if found is None:
            raise NoSuchLibrary("This library plays no games in the portal.")
        return found

    def _box(self) -> SecretBox:
        if self.box is None:
            raise NoSuchLibrary("The portal keeps no secrets here.")
        return self.box

    async def _row(self, holder: UUID, service: UUID) -> LibraryAccount | None:
        async with self.database.session() as session:
            return await session.get(LibraryAccount, (holder, service))

    async def _drop_request(self, holder: UUID, service: UUID) -> None:
        """A request refused or expired: gone — a linked account it would have replaced stays."""
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(LibraryAccount, (holder, service), with_for_update=True)
            if row is None:
                return
            if row.token is None:
                await uow.session.delete(row)
                return
            row.device_code = row.user_code = row.path = None
            row.pending_until = None
            if row.state == "pending":
                row.state = "linked"
            row.updated_at = utc_now(self.clock)
