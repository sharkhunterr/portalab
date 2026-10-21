"""027 — requests to handle: a special request (a film in 4K with the member's wishes) asks for its form,
opens a request due by the product's deadline, and is settled by an administrator — declined, the Coins
come back; a service's access opens a request at once and its approval provisions the account."""

from typing import Any
from uuid import UUID

import pytest

from portalab.core.errors import Conflict, ValidationFailed
from tests.integration.marketplace.conftest import MkHarness, published

FORM = [
    {"key": "title", "type": "text", "labels": {"en": "Film"}, "required": True},
    {"key": "audio", "type": "multi", "options": ["Dolby Atmos", "DTS:X"]},
    {"key": "languages", "type": "text"},
]


async def test_special_request_form_deadline_and_decline_refunds(mk: MkHarness) -> None:
    await published(
        mk,
        "film_4k",
        "special_request",
        price_coins=300,
        payload={"form": FORM, "deadline_days": 5},
    )
    await mk.coins("ursula", 500)
    ursula = mk.p("ursula")
    ownership = await mk.module.purchases.acquire(ursula, "film_4k", "r1")
    assert ownership.state == "needs_configuration"
    with pytest.raises(ValidationFailed):  # the film is required
        from portalab.modules.marketplace.requests.service import answers, form_of

        answers(form_of({"form": FORM}), {"audio": ["Dolby Atmos"]})
    done = await mk.module.activation.configure(
        ursula, ownership.id, {"title": "Dune", "audio": ["Dolby Atmos", "Bogus"], "languages": "VO, VF"}
    )
    assert done.state == "active"
    (mine,) = await mk.module.requests.mine(mk.people["ursula"])
    assert mine.kind == "special" and mine.state == "pending"
    assert mine.details == {"title": "Dune", "audio": ["Dolby Atmos"], "languages": "VO, VF"}
    assert (mine.due_at - mine.created_at).days == 5 and not mine.overdue
    assert await mk.module.requests.open_count() == (1, 0)
    await mk.module.activation.activate(ownership.id)  # re-activation never opens a second one
    assert len(await mk.module.requests.mine(mk.people["ursula"])) == 1

    boss = mk.p("boss")
    started = await mk.module.requests.decide(boss, mine.id, "start", None, False)
    assert started.state == "in_progress"
    with pytest.raises(ValidationFailed):  # a decline says why
        await mk.module.requests.decide(boss, mine.id, "decline", "  ", False)
    assert await mk.balance("ursula") == 200
    declined = await mk.module.requests.decide(boss, mine.id, "decline", "Not in 4K anywhere", False)
    assert declined.state == "declined" and declined.note == "Not in 4K anywhere"
    assert await mk.balance("ursula") == 500  # the Coins came back
    with pytest.raises(Conflict):
        await mk.module.requests.decide(boss, mine.id, "done", None, False)


async def test_service_access_opens_a_request_and_provisions_on_approval(mk: MkHarness) -> None:
    await published(
        mk, "romm_access", "service_access", price_coins=100, payload={"service": "romm", "group": "romm"}
    )
    await mk.coins("ursula", 100)
    provisioned: list[tuple[UUID, dict[str, Any], bool]] = []

    async def provision(user: UUID, details: Any, create: bool) -> str:
        provisioned.append((user, dict(details), create))
        return "account created"

    mk.module.requests.provision = provision
    ownership = await mk.module.purchases.acquire(mk.p("ursula"), "romm_access", "s1")
    assert ownership.state == "active"
    (pending,) = await mk.module.requests.queue(None)
    assert pending.kind == "service" and pending.details == {"service": "romm", "group": "romm"}
    # one member's requests only (their admin card)
    assert [r.id for r in await mk.module.requests.queue(None, user=mk.people["ursula"])] == [pending.id]
    assert await mk.module.requests.queue(None, user=mk.people["boss"]) == []
    done = await mk.module.requests.decide(mk.p("boss"), pending.id, "done", "Welcome!", True)
    assert done.state == "done" and done.details["outcome"] == "account created"
    assert provisioned == [(mk.people["ursula"], {"service": "romm", "group": "romm"}, True)]
    assert await mk.module.requests.queue(None) == []


async def test_approval_creates_the_account_in_the_identity_provider(mk: MkHarness) -> None:
    """027: with Authentik connected, approving a service access finds or creates the member's account and
    puts it in the service's group; without « create », a missing account keeps the request open."""
    from portalab.capabilities.identity_directory import ACCOUNTS, AccountSummary
    from portalab.capabilities.identity_provider import PROVISIONING, SPECS

    calls: list[tuple[str, ...]] = []

    class Sso:
        async def find_user(self, email: str | None, username: str | None) -> str | None:
            return None

        async def create_user(self, username: str, name: str, email: str | None) -> str:
            calls.append(("create", username))
            return "42"

        async def add_to_group(self, user: str, group: str) -> None:
            calls.append(("group", user, group))

        async def remove_from_group(self, user: str, group: str) -> None:
            calls.append(("leave", user, group))

        async def recovery_link(self, user: str) -> str | None:
            return "https://sso.example.org/recovery/x"

    class Accounts:
        async def accounts(self) -> list[AccountSummary]:
            return [AccountSummary(mk.people["ursula"], "ursula", "Ursula", "ursula@example.org")]

    registry = mk.module.capabilities
    if PROVISIONING not in {spec.name for spec in getattr(registry, "_specs", {}).values()}:
        registry.declare(SPECS[0])
    registry.provide(PROVISIONING, Sso(), instance_ref="sso", owner="test")
    if not mk.module.capabilities.system_providers(ACCOUNTS):
        mk.module.capabilities.provide(ACCOUNTS, Accounts(), instance_ref="accounts", owner="test")
    await published(
        mk, "romm_access", "service_access", price_coins=100, payload={"service": "romm", "group": "romm"}
    )
    await mk.coins("ursula", 100)
    await mk.module.purchases.acquire(mk.p("ursula"), "romm_access", "s2")
    (pending,) = await mk.module.requests.queue(None)
    with pytest.raises(Conflict):  # no account and « create » not ticked
        await mk.module.requests.decide(mk.p("boss"), pending.id, "done", None, False)
    done = await mk.module.requests.decide(mk.p("boss"), pending.id, "done", None, True)
    assert done.state == "done" and "account created" in done.details["outcome"]
    assert calls == [("create", "ursula"), ("group", "42", "romm")]


async def test_a_service_opens_only_once_the_terms_are_accepted(mk: MkHarness) -> None:
    """027: approving a service access waits for the member to accept the terms of use in force."""
    from portalab.capabilities.terms import CAPABILITY as TERMS
    from portalab.capabilities.terms import SPEC as TERMS_SPEC

    pending_terms = {"ursula": True}

    class Terms:
        async def must_accept(self, user_id: UUID) -> bool:
            return pending_terms["ursula"] and user_id == mk.people["ursula"]

    registry = mk.module.capabilities
    if TERMS not in {spec.name for spec in getattr(registry, "_specs", {}).values()}:
        registry.declare(TERMS_SPEC)
    providers = registry.system_providers(TERMS)
    if providers:  # the privacy module's own: answer as if the member had not accepted yet
        providers[0].provider.must_accept = Terms().must_accept
    else:
        registry.provide(TERMS, Terms(), instance_ref="terms", owner="test")
    await published(
        mk, "romm_access", "service_access", price_coins=100, payload={"service": "romm", "group": "romm"}
    )
    await mk.coins("ursula", 100)
    mk.module.requests.provision = mk.module._provision  # the module's own, with the terms check
    await mk.module.purchases.acquire(mk.p("ursula"), "romm_access", "t1")
    (pending,) = await mk.module.requests.queue(None)
    with pytest.raises(Conflict) as refused:
        await mk.module.requests.decide(mk.p("boss"), pending.id, "done", None, True)
    assert refused.value.code == "marketplace.terms_pending"
