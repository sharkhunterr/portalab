"""Field-priority reconciler (T024, T035; CD-026, F7).

Priorities are read from the consuming domain's settings shape ``<domain>.fieldPriority.<kind>.<field>``
(Media owns ``media.fieldPriority.*``, spec 024) through the ``admin.config`` reader — connectors declare no
priority setting of their own. A missing or undeclared key means "no preference" for that field.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.record_sink import Reconciled, reconcile
from portalab.capabilities.registry import CapabilityError, CapabilityRegistry


def priority_key(domain: str, kind: str, field: str) -> str:
    return f"{domain}.fieldPriority.{kind}.{field}"


class FieldPriorities:
    def __init__(self, capabilities: CapabilityRegistry, *, domain: str = "media") -> None:
        self.capabilities = capabilities
        self.domain = domain

    async def for_kind(self, kind: str, fields: Iterable[str]) -> dict[str, list[str]]:
        try:
            providers = self.capabilities.system_providers(CONFIG)
        except CapabilityError:
            return {}
        if not providers:
            return {}
        reader = providers[0].provider
        priorities: dict[str, list[str]] = {}
        for field in sorted(set(fields)):
            try:
                value = (await reader.get(priority_key(self.domain, kind, field))).value
            except Exception:  # noqa: S112 — undeclared key or unavailable store: no preference
                continue
            if isinstance(value, list | tuple):
                priorities[field] = [str(item) for item in value]
        return priorities

    async def reconcile(
        self, kind: str, candidates: Mapping[str, Mapping[str, Any]], *, default_order: Sequence[str] = ()
    ) -> Reconciled:
        fields = {name for payload in candidates.values() for name in payload}
        return reconcile(candidates, await self.for_kind(kind, fields), default_order=default_order)
