"""021 T022/T023/T025 — generic registry-driven erasure and export participants; the identity deletion saga
invokes every registered participant."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, String, Table, Uuid, text

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.privacy_registry import pii
from portalab.modules.authz.models import AuditEntry
from portalab.modules.privacy.participants.registry import (
    RegistryErasureParticipant,
    RegistryExportContributor,
    register_registry_participants,
)
from tests.authz_fixtures import insert_user
from tests.privacy_fixtures import FullPlatform

metadata = MetaData(schema="public")
NOTES = Table(
    "notes",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid, ForeignKey("identity.users.id"), nullable=False),
    Column("nickname", String(64), info=pii("profile")),
    Column("motto", String(64), nullable=False, info=pii("profile", tombstone="[deleted]")),
    Column("api_token_hash", String(64)),  # unclassified secret-ish: never exported
)

CREATE = text(
    "CREATE TABLE public.notes (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES identity.users(id), "
    "nickname varchar(64), motto varchar(64) NOT NULL, api_token_hash varchar(64))"
)


async def _seed(full: FullPlatform) -> tuple[UUID, UUID]:
    alice, bob = await insert_user(full.database), await insert_user(full.database)
    async with full.database.engine.begin() as conn:
        await conn.execute(CREATE)
        for owner, nick in ((alice, "ally"), (alice, "al"), (bob, "bobby")):
            await conn.execute(
                text("INSERT INTO public.notes VALUES (:id, :u, :n, 'carpe diem', 'deadbeef')"),
                {"id": uuid4(), "u": owner, "n": nick},
            )
    return alice, bob


async def test_erasure_scrubs_only_classified_columns(full: FullPlatform) -> None:
    alice, bob = await _seed(full)
    participant = RegistryErasureParticipant(full.database, NOTES)
    await participant.erase(alice, "final")
    await participant.erase(alice, "final")  # idempotent
    async with full.database.engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT user_id, nickname, motto, api_token_hash FROM public.notes"))
        ).all()
    mine = [row for row in rows if row.user_id == alice]
    assert len(mine) == 2 and all(row.nickname is None and row.motto == "[deleted]" for row in mine)
    assert all(row.api_token_hash == "deadbeef" for row in mine)  # unclassified, kept (owner's job)
    assert [row.nickname for row in rows if row.user_id == bob] == ["bobby"]


async def test_export_contains_only_my_classified_data(full: FullPlatform) -> None:
    alice, _ = await _seed(full)
    records = await RegistryExportContributor(full.database, NOTES).export(alice)
    assert sorted(record.data["nickname"] for record in records) == ["al", "ally"]
    assert all(set(record.data) == {"nickname", "motto"} for record in records)


def test_append_only_tables_are_refused() -> None:
    with pytest.raises(ValueError):
        RegistryErasureParticipant(None, AuditEntry.__table__)  # type: ignore[arg-type]
    assert AuditEntry.__table__.info.get("portalab_append_only") == APPEND_ONLY_INFO["portalab_append_only"]


async def test_deletion_saga_invokes_registry_participants(full: FullPlatform) -> None:
    alice, _ = await _seed(full)
    register_registry_participants(full.identity.capabilities, full.database, NOTES, owner="test")
    from datetime import timedelta

    from portalab.core.authz_port import Principal
    from portalab.modules.identity.module import IdentityModule
    from portalab.modules.identity.services.common import admin_actor

    identity = IdentityModule(full.identity)
    request = await identity.deletion.request(admin_actor(Principal(user_id=uuid4())), alice, reason="test")
    full.identity.clock.advance(timedelta(days=full.identity.config.deletion_grace_days, seconds=1))  # type: ignore[attr-defined]
    assert await identity.deletion.finalize(request.id)
    async with full.database.engine.connect() as conn:
        nicknames = (
            (await conn.execute(text("SELECT nickname FROM public.notes WHERE user_id = :u"), {"u": alice}))
            .scalars()
            .all()
        )
    assert nicknames == [None, None]
