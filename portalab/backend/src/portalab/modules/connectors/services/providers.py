"""Failure-isolated capability providers (T011, T027; 001 provider isolation).

A connector's live provider is never registered as is: every async member goes through the 001
:class:`ProviderGuard` (timeout, bounded retries, typed results, last-known data served as ``Stale``) and
the service's :class:`CircuitBreaker`. While the circuit is open — or the service is in a blocking condition
— calls are not attempted and the last known data (or ``Unavailable``) is returned. The proxy is a real
class exposing the capability's members, so runtime protocol checks hold.
"""

import inspect
from collections.abc import Callable
from typing import Any

from portalab.capabilities.isolation import ProviderGuard
from portalab.capabilities.results import Available, CapabilityResult, Partial, Unavailable
from portalab.modules.connectors.breaker.breaker import CircuitBreaker
from portalab.modules.connectors.observability import metric_part, metrics


def _members(protocol: type[Any], inner: Any) -> list[str]:
    declared = getattr(protocol, "__protocol_attrs__", None)
    if declared:
        return sorted(declared)
    return sorted(name for name in dir(inner) if not name.startswith("_") and callable(getattr(inner, name)))


def guarded_provider(
    inner: Any,
    protocol: type[Any],
    *,
    capability: str,
    guard: ProviderGuard,
    breaker: CircuitBreaker,
    usable: Callable[[], bool],
) -> Any:
    namespace: dict[str, Any] = {"__slots__": (), "inner": inner}
    for name in _members(protocol, inner):
        member = getattr(inner, name, None)
        if member is None:
            continue
        if not inspect.iscoroutinefunction(member):
            namespace[name] = staticmethod(member) if callable(member) else member
            continue
        namespace[name] = _guarded_method(name, inner, capability, guard, breaker, usable)
    proxy_type = type(f"Guarded{type(inner).__name__}", (), namespace)
    return proxy_type()


def _guarded_method(
    name: str,
    inner: Any,
    capability: str,
    guard: ProviderGuard,
    breaker: CircuitBreaker,
    usable: Callable[[], bool],
) -> Callable[..., Any]:
    metric = f"connectors.calls.{metric_part(capability)}"

    async def call(_self: Any, *args: Any, **kwargs: Any) -> CapabilityResult[Any]:
        key = f"{name}:{args!r}:{sorted(kwargs.items())!r}"
        if not usable() or not breaker.allow():
            metrics.increment(f"{metric}.short_circuited")
            return guard.fallback(key, Unavailable(detail="service unavailable"))
        result: CapabilityResult[Any] = await guard.call(
            lambda: getattr(inner, name)(*args, **kwargs), cache_key=key
        )
        if isinstance(result, Available | Partial):
            await breaker.record_success()
            metrics.increment(f"{metric}.ok")
        else:
            await breaker.record_failure()
            metrics.increment(f"{metric}.failed")
        return result

    call.__name__ = name
    return call
