"""Issue 443: whose rows an administration chart counts, and on whose row — never one gain twice.

Grouped (``economy.household.grouped``): a common pot's profiles are left out (their master holds a copy of
each of their gains), a dispatched profile's gains are drawn on its master's row. Not grouped: each member
on its own row, a master's without the copies of its profiles' gains."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import case, literal, true

from portalab.modules.gamification.models import LedgerTransaction


@dataclass(frozen=True, slots=True)
class ChartScope:
    who: Any  # the chart member a ledger row counts for
    keep: Any  # the ledger rows the chart counts
    dispatched: dict[UUID, UUID] = field(default_factory=dict)  # grouped: a dispatched profile → its master

    def whose(self, member: UUID) -> Any:
        """The rows of one chart member (its dispatched profiles' too, when grouped)."""
        users = [member, *(p for p, owner in self.dispatched.items() if owner == member)]
        return LedgerTransaction.user_id.in_(users) & self.keep


async def chart_scope(module: Any) -> ChartScope:
    household = module._household()
    pot: set[UUID] = set()
    dispatched: dict[UUID, UUID] = {}
    if household is not None:
        try:
            for profile in await household.profiles():
                owner = await household.owner_of(profile)
                if owner is None:
                    continue
                economy = getattr(household, "economy_of", None)
                if economy is None or await economy(profile) == "pot":
                    pot.add(profile)
                else:
                    dispatched[profile] = owner
        except Exception:
            pot, dispatched = set(), {}
    if not module.config.household_grouped:
        return ChartScope(LedgerTransaction.user_id, LedgerTransaction.profile_id.is_(None))
    kind = LedgerTransaction.user_id.type
    who = (
        case(
            *((LedgerTransaction.user_id == p, literal(o, type_=kind)) for p, o in dispatched.items()),
            else_=LedgerTransaction.user_id,
        )
        if dispatched
        else LedgerTransaction.user_id
    )
    keep = LedgerTransaction.user_id.not_in(sorted(pot)) if pot else true()
    return ChartScope(who, keep, dispatched)
