"""025 T022 — the six rule-based detectors on synthetic series, parameters passed in (from config);
a finding is an observation, not an incident."""

from portalab.modules.observability.detectors import rules


def test_error_spike() -> None:
    assert rules.error_spike("sync", 30, [2, 3, 2, 1], factor=3, min_count=5) is not None
    assert rules.error_spike("sync", 4, [0, 0], factor=3, min_count=5) is None  # below the minimum
    assert rules.error_spike("sync", 8, [5, 6, 4], factor=3, min_count=5) is None  # within baseline


def test_long_sync() -> None:
    finding = rules.long_sync("sync:s", 30_000, [8_000, 10_000, 9_000], factor=2)
    assert finding is not None and finding.evidence["median_ms"] == 9_000
    assert rules.long_sync("sync:s", 30_000, [8_000], factor=2) is None  # not enough history


def test_repeated_automation_and_failure() -> None:
    assert rules.repeated_automation("automation:r1", 25, threshold=20) is not None
    assert rules.repeated_automation("automation:r1", 3, threshold=20) is None
    assert rules.repeated_failure("jobs", "e1", 6, count=5) is not None


def test_stuck_consumer_and_latency() -> None:
    stuck = rules.stuck_consumer("events:rewards", 12, 1_200, minutes=15)
    assert stuck is not None and stuck.severity == "critical"
    assert rules.stuck_consumer("events:rewards", 0, 1_200, minutes=15) is None
    assert rules.latency_spike("portal:/x", 900, [100, 120, 110], factor=3) is not None
    assert rules.latency_spike("portal:/x", 200, [100, 120, 110], factor=3) is None


def test_fingerprint_is_stable_per_detector_and_component() -> None:
    a = rules.repeated_automation("automation:r1", 25, threshold=20)
    b = rules.repeated_automation("automation:r1", 40, threshold=20)
    assert a is not None and b is not None and a.fingerprint == b.fingerprint
