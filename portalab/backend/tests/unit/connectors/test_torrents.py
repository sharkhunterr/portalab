"""027 — torrent clients: qBittorrent and Deluge states mapped to the journey's words (a downloading
torrent without speed is « stalled »), hashes cleaned, infinite ETAs dropped; the arr queue tells why a
download waits (manual import, failure)."""

from portalab.connectors.arr import queue_attention, queue_extra
from portalab.connectors.torrents import clean_hashes, map_deluge, map_qbit

HASH = "a" * 40


def test_qbit_mapping() -> None:
    state = map_qbit(
        {
            "hash": HASH.upper(),
            "name": "Film",
            "state": "stalledDL",
            "progress": 0.42,
            "eta": 8640000,
            "dlspeed": 0,
            "num_seeds": 0,
            "num_leechs": 3,
        },
        "qBit",
    )
    assert state is not None
    assert (state.download_id, state.state, state.progress, state.eta_s, state.peers) == (
        HASH,
        "stalled",
        0.42,
        None,
        3,
    )
    assert map_qbit({"hash": HASH, "state": "metaDL"}, "q").state == "metadata"  # type: ignore[union-attr]


def test_deluge_mapping() -> None:
    moving = map_deluge(
        HASH, {"state": "Downloading", "progress": 55.0, "download_payload_rate": 1024, "eta": 60}, "d"
    )
    stuck = map_deluge(HASH, {"state": "Downloading", "progress": 10.0, "download_payload_rate": 0}, "d")
    assert (moving.state, moving.progress, moving.eta_s) == ("downloading", 0.55, 60)
    assert stuck.state == "stalled"


def test_hashes_and_queue() -> None:
    assert clean_hashes([HASH.upper(), "not-a-hash", HASH]) == [HASH]
    record = {
        "downloadId": HASH.upper(),
        "downloadClient": "qBit",
        "title": "Film.2026.1080p",
        "trackedDownloadState": "importBlocked",
        "trackedDownloadStatus": "warning",
        "statusMessages": [{"title": "x", "messages": ["No files found are eligible for import"]}],
        "size": 1000,
    }
    extra = queue_extra(record)
    assert extra["download_id"] == HASH and extra["attention"] == "import_blocked"
    assert extra["messages"] == ("No files found are eligible for import",)
    assert queue_attention({"trackedDownloadState": "downloading"}) is None
