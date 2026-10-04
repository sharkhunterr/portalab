"""Navigation contribution registry (spec 004 T006, T037): validates declarations, rejects duplicates
deterministically (the first registration wins), records rejections for diagnostics, and removes every
contribution of an owner at once (``unregister(owner)``, F20)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from portalab.capabilities.navigation.contribution import NavigationContribution, upgrade_raw
from portalab.capabilities.navigation.sections import FALLBACK_SECTION, NavigationSection

Reason = Literal["schema", "duplicate", "conflict", "runtime"]


@dataclass(frozen=True, slots=True)
class Rejection:
    owner: str
    key: str
    reason: Reason
    detail: str


class NavigationRegistry:
    def __init__(self) -> None:
        self._contributions: dict[str, NavigationContribution] = {}
        self._sections: dict[str, NavigationSection] = {}
        self.rejections: list[Rejection] = []
        self.version = 0  # bumped on every change (part of the navigation cache key)

    def register(
        self, contribution: NavigationContribution | Mapping[str, Any], *, owner: str | None = None
    ) -> NavigationContribution | None:
        raw = (
            contribution.model_dump()
            if isinstance(contribution, NavigationContribution)
            else dict(contribution)
        )
        if owner is not None:
            raw["owner"] = owner
        key, who = str(raw.get("key", "?")), str(raw.get("owner", "?"))
        try:
            parsed = NavigationContribution.model_validate(upgrade_raw(raw))
        except (ValidationError, KeyError, ValueError) as exc:
            errors = exc.errors() if isinstance(exc, ValidationError) else [{"msg": str(exc), "loc": ()}]
            detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors)[:500]
            self.rejections.append(Rejection(who, key, "schema", detail))
            return None
        existing = self._contributions.get(parsed.key)
        if existing is not None:
            if existing == parsed:
                return existing  # idempotent re-registration
            reason: Reason = "duplicate" if existing.owner == parsed.owner else "conflict"
            self.rejections.append(
                Rejection(parsed.owner, parsed.key, reason, f"already declared by {existing.owner}")
            )
            return None
        self._contributions[parsed.key] = parsed
        self.version += 1
        return parsed

    def register_section(
        self, section: NavigationSection | Mapping[str, Any], *, owner: str | None = None
    ) -> NavigationSection | None:
        """Declare a section (027 R1): same rules as contributions — closed schema, first wins."""
        raw = section.model_dump() if isinstance(section, NavigationSection) else dict(section)
        if owner is not None:
            raw["owner"] = owner
        key, who = str(raw.get("key", "?")), str(raw.get("owner", "?"))
        try:
            parsed = NavigationSection.model_validate(raw)
        except (ValidationError, ValueError) as exc:
            errors = exc.errors() if isinstance(exc, ValidationError) else [{"msg": str(exc), "loc": ()}]
            detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors)[:500]
            self.rejections.append(Rejection(who, f"section:{key}", "schema", detail))
            return None
        existing = self._sections.get(parsed.key)
        if existing is not None:
            if existing == parsed:
                return existing
            reason: Reason = "duplicate" if existing.owner == parsed.owner else "conflict"
            self.rejections.append(
                Rejection(
                    parsed.owner, f"section:{parsed.key}", reason, f"already declared by {existing.owner}"
                )
            )
            return None
        self._sections[parsed.key] = parsed
        self.version += 1
        return parsed

    def sections(self) -> list[NavigationSection]:
        return [self._sections[key] for key in sorted(self._sections)]

    def section(self, key: str) -> NavigationSection | None:
        return self._sections.get(key)

    def section_for(self, contribution: NavigationContribution) -> str:
        """The section an entry renders in: its own if registered, else its owner's default, else ``more``."""
        if contribution.group in self._sections:
            return contribution.group
        for section in self.sections():
            if contribution.owner in section.default_for:
                return section.key
        return FALLBACK_SECTION

    def all(self) -> list[NavigationContribution]:
        return [self._contributions[key] for key in sorted(self._contributions)]

    def get(self, key: str) -> NavigationContribution | None:
        return self._contributions.get(key)

    def unregister(self, owner: str) -> int:
        doomed = [key for key, c in self._contributions.items() if c.owner == owner]
        for key in doomed:
            del self._contributions[key]
        sections = [key for key, s in self._sections.items() if s.owner == owner]
        for key in sections:
            del self._sections[key]
        if doomed or sections:
            self.version += 1
        return len(doomed)

    def drain_rejections(self) -> list[Rejection]:
        drained, self.rejections = self.rejections, []
        return drained


default_navigation = NavigationRegistry()


def register_section(section: NavigationSection | Mapping[str, Any]) -> NavigationSection | None:
    return default_navigation.register_section(section)


def register_contribution(
    contribution: NavigationContribution | Mapping[str, Any], *, owner: str | None = None
) -> NavigationContribution | None:
    return default_navigation.register(contribution, owner=owner)
