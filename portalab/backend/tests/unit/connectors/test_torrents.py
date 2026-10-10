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


class _Answer:
    def __init__(self, body: dict[str, object], headers: dict[str, str] | None = None) -> None:
        self.status_code = 200
        self.body = body
        self.headers = headers or {}

    def json(self) -> dict[str, object]:
        return self.body


class _Deluge2:
    """A Deluge 2 Web UI: ``daemon.info`` is gone (``daemon.get_version`` instead)."""

    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.calls: list[str] = []

    async def request(self, method: str, path: str, **kwargs: object) -> _Answer:
        call = kwargs["json"]
        assert isinstance(call, dict)
        name = str(call["method"])
        self.calls.append(name)
        if name == "auth.login":
            return _Answer({"result": True, "error": None}, {"set-cookie": "_session_id=abc; Path=/json"})
        if name == "web.connected":
            return _Answer({"result": self.connected, "error": None})
        if name == "web.get_hosts":
            return _Answer({"result": [], "error": None})
        if name == "daemon.get_version" and self.connected:
            return _Answer({"result": "2.1.1", "error": None})
        return _Answer({"result": None, "error": {"message": f"Unknown method {name}", "code": 2}})


async def test_deluge_2_connects() -> None:
    from uuid import uuid4

    from portalab.capabilities.connector_sdk import ServiceHandle
    from portalab.connectors.torrents import DelugeConnector

    http = _Deluge2()
    service = ServiceHandle(uuid4(), "Deluge", {}, {"password": "x"}, http)
    result = await DelugeConnector().test_connection(service)
    assert result.ok and result.detail == "Connected to Deluge 2.1.1."

    # no daemon behind the Web UI: reachable and authenticated, the reason said
    lonely = ServiceHandle(uuid4(), "Deluge", {}, {"password": "x"}, _Deluge2(connected=False))
    result = await DelugeConnector().test_connection(lonely)
    assert not result.ok and result.reachable and "daemon" in result.detail
