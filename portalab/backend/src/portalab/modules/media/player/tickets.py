"""A started stream's **ticket** (027, #2): who plays what, where, signed by the portal.

The browser's player addresses every playlist, segment and subtitle request with it; the portal checks the
signature, the expiry and that the ticket is the requesting member's own. Nothing is kept in memory, so
any process of the portal can relay any stream.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import UUID

from portalab.capabilities.media import StreamOptions
from portalab.core.errors import NotFound

LIFETIME_S = 12 * 3600
REMOTE_LIFETIME_S = 8 * 3600


def remote_key(key: bytes) -> bytes:
    """027 (#11): the key of **remote** tickets — the URL a Chromecast or an Apple TV fetches the stream
    with, without the member's session. Distinct from the player's, so neither ticket opens the other's
    door."""
    return hmac.new(key, b"portalab.media.player.remote", hashlib.sha256).digest()


class TicketInvalid(NotFound):
    default_code = "media.player_expired"
    default_title = "This stream has ended"


@dataclass(frozen=True, slots=True)
class Ticket:
    user: UUID
    service: UUID
    account: str | None  # the member's account on the service (``None``: the service's own)
    item: str  # the title's id on the service
    session: str  # the service's stream session
    options: StreamOptions
    duration_s: float | None
    expires: int  # epoch seconds


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(key: bytes, ticket: Ticket) -> str:
    body = {
        "u": str(ticket.user),
        "s": str(ticket.service),
        "a": ticket.account,
        "i": ticket.item,
        "x": ticket.session,
        "o": asdict(ticket.options),
        "d": ticket.duration_s,
        "e": ticket.expires,
    }
    payload = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    mac = hmac.new(key, payload.encode(), hashlib.sha256).digest()[:18]
    return f"{payload}.{_b64(mac)}"


def read(key: bytes, token: str, *, user: UUID | None, now: datetime) -> Ticket:
    """``user=None`` for a remote ticket: the device holding it has no session (its bearer is the key)."""
    payload, _, mac = token.partition(".")
    try:
        expected = hmac.new(key, payload.encode(), hashlib.sha256).digest()[:18]
        if not mac or not hmac.compare_digest(expected, _unb64(mac)):
            raise ValueError("bad signature")
        body = json.loads(_unb64(payload))
        ticket = Ticket(
            user=UUID(body["u"]),
            service=UUID(body["s"]),
            account=body["a"],
            item=str(body["i"]),
            session=str(body["x"]),
            options=StreamOptions(**body["o"]),
            duration_s=body["d"],
            expires=int(body["e"]),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise TicketInvalid("This stream does not exist.") from exc
    if (user is not None and ticket.user != user) or ticket.expires < now.timestamp():
        raise TicketInvalid("This stream has ended.")
    return ticket
