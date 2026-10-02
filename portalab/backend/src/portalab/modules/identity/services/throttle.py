"""Login throttling — progressive delay per (identifier, ip prefix), never a lockout (research R5).

The key is a hash: no raw identifier is stored. The delay doubles after ``FREE_ATTEMPTS`` failures and is
capped at ``MAX_DELAY``, so the Admin can never be locked out for good, and attempts from another network
are throttled independently. A successful sign-in clears the key.
"""

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.identity.models import LoginThrottle

FREE_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)
BASE_DELAY = timedelta(seconds=2)
MAX_DELAY = timedelta(minutes=15)


def throttle_key(identifier: str, client_prefix: str | None) -> str:
    material = f"{identifier.strip().casefold()}|{client_prefix or '-'}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def delay_after(failures: int) -> timedelta:
    if failures < FREE_ATTEMPTS:
        return timedelta(0)
    exponent = min(failures - FREE_ATTEMPTS, 20)  # bounded: no overflow under a sustained attack
    delay: timedelta = min(BASE_DELAY * (2**exponent), MAX_DELAY)
    return delay


class LoginThrottleService:
    async def blocked_until(self, session: AsyncSession, key: str, now: datetime) -> datetime | None:
        row = await session.get(LoginThrottle, key)
        if row is None or row.blocked_until is None or row.blocked_until <= now:
            return None
        return row.blocked_until

    async def record_failure(self, session: AsyncSession, key: str, now: datetime) -> datetime | None:
        row = await session.get(LoginThrottle, key, with_for_update=True)
        if row is None:
            await session.execute(
                insert(LoginThrottle)
                .values(key_hash=key, failures=0, window_start=now, blocked_until=None)
                .on_conflict_do_nothing(index_elements=["key_hash"])
            )
            row = await session.get(LoginThrottle, key, with_for_update=True, populate_existing=True)
            assert row is not None
        if now - row.window_start > WINDOW and (row.blocked_until is None or row.blocked_until <= now):
            row.failures = 0
            row.window_start = now
        row.failures += 1
        delay = delay_after(row.failures)
        row.blocked_until = now + delay if delay else None
        await session.flush()
        return row.blocked_until

    async def clear(self, session: AsyncSession, key: str) -> None:
        await session.execute(delete(LoginThrottle).where(LoginThrottle.key_hash == key))
