"""A listening or reading **ticket** (#20, #21): who listens to or reads what, where, signed by the portal.

The browser's audio element and reader address the relayed file with it — the audio, an EPUB or a PDF, a
comic's pages — and report where the member is. Nothing is kept in memory: any process relays any ticket.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from portalab.core.errors import NotFound

LIFETIME_S = 24 * 3600


def books_key(key: bytes) -> bytes:
    """Distinct from the video player's: neither ticket opens the other's door."""
    return hmac.new(key, b"portalab.media.books", hashlib.sha256).digest()


class BookTicketInvalid(NotFound):
    default_code = "media.book_expired"
    default_title = "This book is no longer open"


@dataclass(frozen=True, slots=True)
class BookTicket:
    user: UUID
    service: UUID
    account: str | None  # the member's linked account on the service (``None``: not linked)
    object_id: UUID
    item: str  # the book's id on the service
    mode: str  # listen | read
    session: str  # one listening or reading session (its events share it)
    expires: int  # epoch seconds
    file: str | None = None  # the audio file's id on the service (its progress is kept per file)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(key: bytes, ticket: BookTicket) -> str:
    body = {
        "u": str(ticket.user),
        "s": str(ticket.service),
        "a": ticket.account,
        "o": str(ticket.object_id),
        "i": ticket.item,
        "m": ticket.mode,
        "x": ticket.session,
        "e": ticket.expires,
        "f": ticket.file,
    }
    payload = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    mac = hmac.new(key, payload.encode(), hashlib.sha256).digest()[:18]
    return f"{payload}.{_b64(mac)}"


def read(key: bytes, token: str, *, user: UUID, mode: str, now: datetime) -> BookTicket:
    payload, _, mac = token.partition(".")
    try:
        expected = hmac.new(key, payload.encode(), hashlib.sha256).digest()[:18]
        if not mac or not hmac.compare_digest(expected, _unb64(mac)):
            raise ValueError("bad signature")
        body = json.loads(_unb64(payload))
        ticket = BookTicket(
            user=UUID(body["u"]),
            service=UUID(body["s"]),
            account=body["a"],
            object_id=UUID(body["o"]),
            item=str(body["i"]),
            mode=str(body["m"]),
            session=str(body["x"]),
            expires=int(body["e"]),
            file=body.get("f"),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise BookTicketInvalid("This book is not open.") from exc
    if ticket.user != user or ticket.mode != mode or ticket.expires < now.timestamp():
        raise BookTicketInvalid("This book is no longer open.")
    return ticket
