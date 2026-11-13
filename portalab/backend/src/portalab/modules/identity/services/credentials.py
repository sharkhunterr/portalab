"""Local credential store — Argon2id (research R2).

* per-hash salt, parameters from ``identity.argon2Params``; a parameter change re-hashes on next sign-in;
* unknown logins are verified against a dummy hash so the work (and timing) matches the real path (R4);
* hashing runs in a worker thread: Argon2 is deliberately CPU/memory hard.
"""

import gzip
import secrets
from collections.abc import Iterable
from datetime import datetime
from functools import cache
from pathlib import Path
from uuid import UUID

import anyio
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.errors import ValidationFailed
from portalab.modules.identity.models import Credential
from portalab.modules.identity.settings import Argon2Params, PasswordPolicy

SCHEME = "argon2id"
# #276: at most this many Argon2 computations at once (64 MiB each) — a burst of sign-ins queues instead of
# taking the server's memory
CONCURRENT_HASHES = 4


class PasswordRejected(ValidationFailed):
    default_code = "user.password_invalid"
    default_title = "Password does not meet the policy"


def params_version(params: Argon2Params) -> str:
    return f"t{params.time_cost}-m{params.memory_cost_kib}-p{params.parallelism}"


COMMON = Path(__file__).resolve().parents[1] / "data" / "common-passwords.txt.gz"


@cache
def common_passwords() -> frozenset[str]:
    """Issue 406: the passwords most used in data breaches (NCSC's 100k, the 8+ characters ones)."""
    try:
        with gzip.open(COMMON, "rt", encoding="utf-8") as listed:
            return frozenset(line.strip() for line in listed if line.strip())
    except OSError:  # never without it in a build; a missing file must not lock members out
        return frozenset()


def check_password_policy(password: str, policy: PasswordPolicy, *, personal: Iterable[str] = ()) -> None:
    """Length, not blank — and (issue 406, ASVS 6.2.4 and 6.2.11) neither a password found in data breaches
    nor one holding the member's own login or name."""
    if not policy.min_length <= len(password) <= policy.max_length:
        raise PasswordRejected(
            f"Use a password of {policy.min_length} to {policy.max_length} characters.",
            extensions={"min_length": policy.min_length, "max_length": policy.max_length},
        )
    if password.strip() == "":
        raise PasswordRejected("A password cannot be blank.")
    lowered = password.lower()
    if lowered in common_passwords():
        raise PasswordRejected(
            "This password is among the most used ones found in data breaches: choose another.",
            code="user.password_common",
        )
    for word in personal:
        word = (word or "").strip().lower()
        if len(word) >= 3 and word in lowered:
            raise PasswordRejected(
                "A password cannot hold your login or your name.", code="user.password_personal"
            )


class CredentialHasher:
    def __init__(self, params: Argon2Params) -> None:
        self.params = params
        self.version = params_version(params)
        self._hasher = PasswordHasher(
            time_cost=params.time_cost,
            memory_cost=params.memory_cost_kib,
            parallelism=params.parallelism,
            type=Type.ID,
        )
        # verifying against this hash costs the same as a real verification
        self._dummy = self._hasher.hash(secrets.token_urlsafe(24))
        self._limiter: anyio.CapacityLimiter | None = None

    @property
    def limiter(self) -> anyio.CapacityLimiter:
        if self._limiter is None:  # made in the event loop, on first use
            self._limiter = anyio.CapacityLimiter(CONCURRENT_HASHES)
        return self._limiter

    async def hash(self, password: str) -> str:
        return await anyio.to_thread.run_sync(self._hasher.hash, password, limiter=self.limiter)

    def _verify(self, stored: str, password: str) -> bool:
        try:
            return bool(self._hasher.verify(stored, password))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    async def verify(self, stored: str | None, password: str) -> bool:
        """Constant-work verification; ``stored=None`` (unknown login) always fails after the same work."""
        if stored is None:
            await anyio.to_thread.run_sync(self._verify, self._dummy, password, limiter=self.limiter)
            return False
        return await anyio.to_thread.run_sync(self._verify, stored, password, limiter=self.limiter)

    def needs_rehash(self, stored: str) -> bool:
        try:
            return bool(self._hasher.check_needs_rehash(stored))
        except InvalidHashError:
            return True


async def set_password(
    session: AsyncSession, hasher: CredentialHasher, user_id: UUID, password: str, now: datetime
) -> None:
    hashed = await hasher.hash(password)
    credential = await session.get(Credential, user_id)
    if credential is None:
        session.add(
            Credential(
                user_id=user_id, scheme=SCHEME, hash=hashed, params_version=hasher.version, changed_at=now
            )
        )
    else:
        credential.hash = hashed
        credential.params_version = hasher.version
        credential.changed_at = now
    await session.flush()
