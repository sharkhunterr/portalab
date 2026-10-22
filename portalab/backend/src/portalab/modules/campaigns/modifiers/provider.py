"""``economy.modifiers`` for Gamification (T020; R7): for an occurrence at ``at`` — campaigns active at that
instant, their version in force, audience and conditions — one ``Modifier`` per matched campaign modifier
(at most once per occurrence) with the reference ``campaign:<key>:<version>:<modifier>``. Campaigns supply
**factors only**: combination and the cap are Gamification's (CD-024).

Issue 223: a title is rewarded once by a campaign's *themed* bonuses (by genre, title, keyword or hand-picked
titles): a horror film whose keywords also say Halloween earns the best of them, not both. A campaign's
general bonuses (every play, every film) still add up with them."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from portalab.capabilities.economy import Modifier, Value
from portalab.capabilities.events import Envelope
from portalab.modules.campaigns.definitions.schema import When
from portalab.modules.campaigns.matching.conditions import Matcher, match_attributes, needs_attributes
from portalab.modules.campaigns.observability import metrics
from portalab.modules.campaigns.resolver.active import ActiveResolver


@dataclass(frozen=True, slots=True)
class Explanation:
    campaign: str
    version: int
    modifier: str
    value: str
    factor: float
    verdict: str  # match | no_match | unknown | audience | value | covered
    themed: bool = False


def themed(when: When) -> bool:
    """A bonus about *what* is played (a genre, titles, keywords, picked titles), not about every play."""
    return bool(when.genre or when.title_contains or when.keyword or when.objects)


def _once_per_title(found: list[Explanation]) -> list[Explanation]:
    """Of a campaign's themed bonuses matching for one value, the best applies; the others are ``covered``."""
    best: dict[tuple[str, str], Explanation] = {}
    for item in found:
        if item.themed and item.verdict == "match":
            key = (item.campaign, item.value)
            if key not in best or item.factor > best[key].factor:
                best[key] = item
    return [
        item
        if not (item.themed and item.verdict == "match") or best[(item.campaign, item.value)] is item
        else replace(item, verdict="covered")
        for item in found
    ]


class CampaignModifiers:
    def __init__(self, resolver: ActiveResolver, matcher: Matcher) -> None:
        self.resolver = resolver
        self.matcher = matcher

    async def explain(self, user: UUID, event: Envelope, at: datetime) -> list[Explanation]:
        out: list[Explanation] = []
        active = await self.resolver.at(at)
        attributes = None
        if any(needs_attributes(m.when) for c in active for m in c.definition.modifiers):
            attributes = await self.matcher.attributes(event.type, event.payload)
        for campaign in active:
            for modifier in campaign.definition.modifiers:
                verdict: str
                if modifier.when.activity and event.type not in modifier.when.activity:
                    verdict = "no_match"
                elif not await self.matcher.in_audience(modifier.when.audience, user):
                    verdict = "audience"
                else:
                    verdict = match_attributes(modifier.when, attributes)
                for gain in modifier.all_gains():
                    out.append(
                        Explanation(
                            campaign.key,
                            campaign.version,
                            modifier.id,
                            gain.value,
                            gain.factor,
                            verdict,
                            themed(modifier.when),
                        )
                    )
        return _once_per_title(out)

    async def modifiers_for(
        self, user: UUID, event: Envelope, value: Value, at: datetime
    ) -> Sequence[Modifier]:
        found = []
        for item in await self.explain(user, event, at):
            if item.value != value:
                continue
            metrics.increment(f"campaigns.conditions.{item.verdict}")
            if item.verdict == "match":
                found.append(
                    Modifier(f"campaign:{item.campaign}:{item.version}:{item.modifier}", item.factor)
                )
        return found
