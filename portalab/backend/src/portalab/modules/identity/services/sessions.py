"""Server-side sessions (research R1): opaque 256-bit token, only its SHA-256 stored, idle + absolute expiry.

Sessions are revocable immediately (logout, suspension, deletion, admin action); permissions are evaluated
per request, so a revoked or demoted user never keeps stale rights. The CSRF token is derived from the
session token (double-submit bound to the session, research R6), so it needs no storage.
"""

import hashlib
import hmac
import ipaddress
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.identity.models import UserSession
from portalab.modules.identity.settings import IdentityConfig

TOKEN_BYTES = 32
LAST_SEEN_GRANULARITY = timedelta(minutes=1)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def csrf_token_for(session_token: str) -> str:
    return hashlib.sha256(b"portalab-csrf:" + session_token.encode("utf-8")).hexdigest()


def csrf_matches(session_token: str, presented: str | None) -> bool:
    return presented is not None and hmac.compare_digest(csrf_token_for(session_token), presented)


def ip_prefix(address: str | None) -> str | None:
    """Truncated client address (IPv4 /24, IPv6 /48) — enough for abuse analysis, not for tracking."""
    if not address:
        return None
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    prefix = 24 if ip.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def summarize_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return user_agent.split(" ", 1)[0][:128]


@dataclass(frozen=True, slots=True)
class IssuedSession:
    session_id: UUID
    token: str
    csrf_token: str
    expires_at: datetime


class SessionService:
    def __init__(self, config: IdentityConfig) -> None:
        self.config = config

    def _expiry(self, created_at: datetime, last_seen_at: datetime) -> datetime:
        idle = last_seen_at + timedelta(minutes=self.config.session_idle_minutes)
        absolute = created_at + timedelta(hours=self.config.session_absolute_hours)
        return min(idle, absolute)

    async def create(
        self,
        session: AsyncSession,
        user_id: UUID,
        now: datetime,
        *,
        user_agent: str | None = None,
        client_ip: str | None = None,
    ) -> IssuedSession:
        token = new_token()
        row = UserSession(
            token_hash=hash_token(token),
            user_id=user_id,
            created_at=now,
            last_seen_at=now,
            expires_at=self._expiry(now, now),
            user_agent_summary=summarize_user_agent(user_agent),
            ip_prefix=ip_prefix(client_ip),
        )
        session.add(row)
        await session.flush()
        return IssuedSession(row.id, token, csrf_token_for(token), row.expires_at)

    async def resolve(self, session: AsyncSession, token: str, now: datetime) -> UserSession | None:
        """The live session for ``token`` (sliding idle expiry), or ``None``."""
        row = (
            await session.execute(select(UserSession).where(UserSession.token_hash == hash_token(token)))
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None or row.expires_at <= now:
            return None
        if now - row.last_seen_at >= LAST_SEEN_GRANULARITY:
            row.last_seen_at = now
            row.expires_at = self._expiry(row.created_at, now)
        return row

    async def revoke(self, session: AsyncSession, session_id: UUID, now: datetime, reason: str) -> bool:
        result = await session.execute(
            update(UserSession)
            .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason)
        )
        return bool(getattr(result, "rowcount", 0))

    async def revoke_all(
        self,
        session: AsyncSession,
        user_id: UUID,
        now: datetime,
        reason: str,
        *,
        except_id: UUID | None = None,
    ) -> int:
        statement = update(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
        )
        if except_id is not None:
            statement = statement.where(UserSession.id != except_id)
        result = await session.execute(statement.values(revoked_at=now, revoke_reason=reason))
        return int(getattr(result, "rowcount", 0) or 0)
