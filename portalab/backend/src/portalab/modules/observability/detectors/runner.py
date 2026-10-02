"""Detector runner (T024): gathers the series each rule needs from the observability store and the
``events.stats`` capability, runs every rule in isolation (a failing detector is counted, never fatal)
and hands findings to escalation."""

from collections import defaultdict
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from portalab.capabilities.events import STATS_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.detectors import rules
from portalab.modules.observability.detectors.rules import Finding
from portalab.modules.observability.models import ErrorRecord, MetricSample
from portalab.modules.observability.observability import log, metric_part, metrics
from portalab.modules.observability.settings import ObservabilityConfig

WINDOW = timedelta(hours=1)
BASELINE = timedelta(hours=24)


class DetectorRunner:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        config: Callable[[], ObservabilityConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = config
        self.clock = clock

    async def _samples(self, metric: str, since: Any) -> list[MetricSample]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(MetricSample).where(
                            MetricSample.metric == metric, MetricSample.sampled_at >= since
                        )
                    )
                ).scalars()
            )

    async def detect(self) -> list[Finding]:
        findings: list[Finding] = []
        for name, detector in (
            ("error_spike", self._error_spikes),
            ("long_sync", self._long_syncs),
            ("repeated_automation", self._repeated_automations),
            ("stuck_consumer", self._stuck_consumers),
            ("latency_spike", self._latency_spikes),
            ("repeated_failure", self._repeated_failures),
        ):
            try:
                findings.extend(await detector())
            except Exception:
                metrics.increment(f"observability.detector_failures.{metric_part(name)}")
                log.warning("detector failed", extra={"fields": {"detector": name}})
        return findings

    async def _error_spikes(self) -> list[Finding]:
        now, cfg = utc_now(self.clock), self.config()
        hourly: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for sample in await self._samples("errors.recorded", now - BASELINE - WINDOW):
            hours_ago = int((now - sample.sampled_at) // WINDOW)
            hourly[sample.component][hours_ago] += sample.count
        found = []
        for component, buckets in hourly.items():
            baseline = [buckets.get(h, 0) for h in range(1, 25)]
            finding = rules.error_spike(
                component,
                buckets.get(0, 0),
                baseline,
                factor=cfg.error_spike_factor,
                min_count=cfg.error_spike_min_count,
            )
            if finding:
                found.append(finding)
        return found

    async def _long_syncs(self) -> list[Finding]:
        now, cfg = utc_now(self.clock), self.config()
        series: dict[str, list[tuple[Any, float]]] = defaultdict(list)
        for sample in await self._samples("sync.duration", now - 7 * BASELINE):
            service = str(sample.labels.get("service", ""))
            series[service].append((sample.sampled_at, sample.max if sample.max is not None else sample.sum))
        found = []
        for service, points in series.items():
            points.sort()
            latest_at, latest = points[-1]
            if now - latest_at > WINDOW:
                continue
            finding = rules.long_sync(
                f"sync:{service}", latest, [v for _, v in points[:-1]], factor=cfg.long_sync_factor
            )
            if finding:
                found.append(finding)
        return found

    async def _repeated_automations(self) -> list[Finding]:
        now, cfg = utc_now(self.clock), self.config()
        counts: dict[str, int] = defaultdict(int)
        for sample in await self._samples("automation.execution", now - WINDOW):
            counts[str(sample.labels.get("rule", "?"))] += sample.count
        found = []
        for rule, executions in counts.items():
            finding = rules.repeated_automation(
                f"automation:{rule}", executions, threshold=cfg.repeated_automation_threshold
            )
            if finding:
                found.append(finding)
        return found

    async def _stuck_consumers(self) -> list[Finding]:
        providers = self.capabilities.system_providers(STATS_CAPABILITY)
        if not providers:
            return []
        snap = await providers[0].provider.snapshot()
        minutes = self.config().stuck_consumer_minutes
        found = []
        for consumer, lag in snap.lag_by_consumer.items():
            finding = rules.stuck_consumer(
                f"events:{consumer}", lag, snap.oldest_failure_age_seconds, minutes=minutes
            )
            if finding:
                found.append(finding)
        return found

    async def _latency_spikes(self) -> list[Finding]:
        now, cfg = utc_now(self.clock), self.config()
        series: dict[str, dict[int, float]] = defaultdict(dict)
        for sample in await self._samples("http.request", now - BASELINE - WINDOW):
            if sample.labels.get("phase") != "internal" or sample.p95 is None:
                continue
            key = f"{sample.component}:{sample.labels.get('route', '?')}"
            hours_ago = int((now - sample.sampled_at) // WINDOW)
            series[key][hours_ago] = max(series[key].get(hours_ago, 0.0), sample.p95)
        found = []
        for key, buckets in series.items():
            baseline = [buckets[h] for h in range(1, 25) if h in buckets]
            finding = rules.latency_spike(key, buckets.get(0), baseline, factor=cfg.latency_spike_factor)
            if finding:
                found.append(finding)
        return found

    async def _repeated_failures(self) -> list[Finding]:
        now, cfg = utc_now(self.clock), self.config()
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(ErrorRecord).where(
                        ErrorRecord.state == "open", ErrorRecord.last_seen_at >= now - WINDOW
                    )
                )
            ).scalars()
            found = []
            for row in rows:
                finding = rules.repeated_failure(
                    row.component, str(row.id), row.count, count=cfg.repeated_failure_count
                )
                if finding:
                    found.append(
                        Finding(
                            finding.detector,
                            f"{row.component}:{row.fingerprint[:12]}",
                            finding.severity,
                            finding.summary,
                            finding.evidence,
                        )
                    )
        return found
