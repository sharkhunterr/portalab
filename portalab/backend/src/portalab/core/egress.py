"""The outbound allow-list (spec 030, FR-024, issue 144): when the Admin switches it on, Portalab's outgoing
HTTP calls reach only the hosts it knows — those listed in ``security.egress.hosts`` and those its own
configuration declares (a configured service, a sign-in provider, the pack sources, an AI provider, a plugin's
hosts the Admin accepted). Any other call is refused before it leaves, logged and counted; a flaw that would
make Portalab call somewhere else (a request forged by an attacker, a module gone wrong) stops here.

Every ``httpx`` client Portalab makes passes ``event_hooks=egress.hooks()``.
"""

import fnmatch
from collections import defaultdict
from typing import Any

import httpx

from portalab.core.logging import get_logger
from portalab.core.metrics import default_metrics

log = get_logger("portalab.egress")


class EgressRefused(httpx.TransportError):
    """An outgoing call to a host the allow-list does not hold."""


class EgressPolicy:
    def __init__(self) -> None:
        self.enabled = False
        self.listed: set[str] = set()
        self.declared: dict[str, set[str]] = defaultdict(set)

    def configure(self, *, enabled: bool, hosts: list[str] | tuple[str, ...] = ()) -> None:
        self.enabled = bool(enabled)
        self.listed = {str(h).strip().lower() for h in hosts if str(h).strip()}

    def allow(self, host: str | None, reason: str) -> None:
        """A host Portalab's configuration declares (a service's address, a provider's…)."""
        if host:
            self.declared[host.strip().lower()].add(reason)

    def forget(self, reason: str) -> None:
        for host in list(self.declared):
            self.declared[host].discard(reason)
            if not self.declared[host]:
                del self.declared[host]

    def allowed(self, host: str | None) -> bool:
        if not self.enabled:
            return True
        name = (host or "").strip().lower()
        if not name:
            return False
        if name in self.declared or name in self.listed:
            return True
        return any("*" in pattern and fnmatch.fnmatch(name, pattern) for pattern in self.listed)

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "listed": sorted(self.listed),
            "declared": {host: sorted(reasons) for host, reasons in sorted(self.declared.items())},
        }


EGRESS = EgressPolicy()


async def _check(request: httpx.Request) -> None:
    # issue 401: a caller that resolved and checked a name itself connects to its address — the name it is
    # for comes in the request's ``egress_host`` extension, set by Portalab's code, never by a header
    host = str(request.extensions.get("egress_host") or request.url.host)
    if not EGRESS.allowed(host):
        default_metrics.counter("security", "egress.refused")
        log.warning("outgoing call refused", extra={"fields": {"host": host[:120]}})
        raise EgressRefused(f"{host} is not on the outbound allow-list", request=request)


def hooks() -> dict[str, list[Any]]:
    """``event_hooks`` for an ``httpx.AsyncClient``: the allow-list checked before every request."""
    return {"request": [_check]}
