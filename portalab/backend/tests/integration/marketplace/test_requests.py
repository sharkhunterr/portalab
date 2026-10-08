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
    done = await mk.module.requests.decide(mk.p("boss"), pending.id, "done", "Welcome!", True)
    assert done.state == "done" and done.details["outcome"] == "account created"
    assert provisioned == [(mk.people["ursula"], {"service": "romm", "group": "romm"}, True)]
    assert await mk.module.requests.queue(None) == []
