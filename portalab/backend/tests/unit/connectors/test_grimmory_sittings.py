"""#385, #386 — Grimmory's listening sittings: its pieces of a few minutes (same start) make one sitting, a
sitting still growing is not over, and the latest sitting reaches the book's own progress (its audio pieces
tell none)."""

from datetime import UTC, datetime, timedelta

import pytest

from portalab.connectors.grimmory import book_progress, knows_progress, sittings

START = "2026-11-09T05:47:14Z"
BOOK = {
    "id": 1348,
    "primaryFile": {"bookType": "AUDIOBOOK"},
    "metadata": {"title": "Alien", "authors": ["Tim Lebbon"]},
}
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def piece(ref: int, end: str, seconds: float, start: str = START, **fields: object) -> dict[str, object]:
    return {
        "id": ref,
        "bookId": 1348,
        "bookType": "AUDIOBOOK",
        "startTime": start,
        "endTime": end,
        "durationSeconds": seconds,
        **fields,
    }


MORNING = [  # Grimmory's pieces, not in order
    piece(78, "2026-11-09T06:02:14Z", 300),
    piece(76, "2026-11-09T05:52:14Z", 300),
    piece(85, "2026-11-09T06:40:58Z", 136),
    piece(77, "2026-11-09T05:57:14Z", 300),
]


def test_the_pieces_of_a_sitting_make_one_activity():
    (sitting,) = sittings(MORNING, BOOK, "9", NOW)
    assert sitting.ref == "76"  # the first piece's: it stays while the sitting grows
    assert sitting.kind == "audiobook"
    assert sitting.started_at == datetime(2026, 11, 9, 5, 47, 14, tzinfo=UTC)
    assert sitting.stopped_at == datetime(2026, 11, 9, 6, 40, 58, tzinfo=UTC)
    assert sitting.watched_s == 1036
    assert sitting.progress is None


def test_sittings_of_other_starts_stay_apart_in_order():
    other = piece(90, "2026-11-10T07:10:00Z", 600, start="2026-11-10T07:00:00Z")
    first, second = sittings([other, *MORNING], BOOK, "9", NOW + timedelta(days=2))
    assert (first.ref, second.ref) == ("76", "90")
    assert second.watched_s == 600


def test_a_sitting_still_growing_is_not_over():
    (sitting,) = sittings(MORNING, BOOK, "9", datetime(2026, 11, 9, 6, 45, tzinfo=UTC))
    assert sitting.stopped_at is None  # its last piece is 4 minutes old: still listening
    assert sitting.watched_s == 1036


def test_the_latest_sitting_reaches_the_books_progress():
    other = piece(60, "2026-11-05T06:30:00Z", 600, start="2026-11-05T06:20:00Z")
    earlier, latest = sittings([other, *MORNING], BOOK, "9", NOW, progress=1.0)
    assert latest.progress == 1.0
    assert earlier.progress is None  # only the latest sitting is where the book is now


def test_a_pieces_own_progress_is_kept_when_further():
    reading = [piece(5, "2026-11-09T06:00:00Z", 300, bookType="EPUB", endProgress=80.0)]
    (sitting,) = sittings(reading, {"id": 2, "metadata": {"title": "Dune"}}, "9", NOW, progress=0.5)
    assert sitting.progress == 0.8


def test_the_books_progress():
    assert book_progress({"audiobookProgress": {"percentage": 99.4}}) == pytest.approx(0.994)
    assert book_progress({"readStatus": "READ", "audiobookProgress": {"percentage": 12.0}}) == 1.0
    assert book_progress({"epubProgress": {"percentage": 30}, "pdfProgress": {"percentage": 45}}) == 0.45
    assert book_progress({"readStatus": "READING"}) is None
    assert knows_progress({"readStatus": "READING"}) and not knows_progress(BOOK)
