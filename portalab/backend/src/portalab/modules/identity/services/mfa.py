"""Two-factor authentication (issue 408, ASVS 6.5): a time-based one-time password (TOTP, RFC 6238 — the
codes of any authenticator app) for local accounts, and ten single-use recovery codes.

* the secret is kept encrypted (the application key); a code is accepted once (its time step is kept) and
  only from the current step or its neighbours (a clock a little off);
* setting it up, turning it off and making new recovery codes ask for the password again;
* a sign-in with a right password and a second factor waits on a challenge — a few minutes, five attempts,
  used once, only its SHA-256 kept — and no session exists before the second factor;
* a single sign-on is left to the provider's own second factor.
"""

import base64
import hashlib
import hmac
import io
import secrets
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, Unauthorized, ValidationFailed
from portalab.core.secrets import SecretBox
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.models import MfaChallenge, RecoveryCode, TotpFactor, User
from portalab.modules.identity.services.auth import AuthService
from portalab.modules.identity.services.common import (
    InvalidCredentials,
    SoleAdminProtected,
    Throttled,
    audit,
    publish,
    user_ref,
)

STEP = 30  # seconds per code (RFC 6238's default, what every app shows)
DIGITS = 6
WINDOW = 1  # the step before and after the current one are accepted too
RECOVERY_CODES = 10
CHALLENGE_TTL = timedelta(minutes=5)
CHALLENGE_ATTEMPTS = 5
RECENT = timedelta(minutes=15)  # wrong codes counted per account over this, whatever the challenge
RECENT_ATTEMPTS = 10
CONTEXT = "identity.totp"  # the encrypted secret's associated data


class SecondFactorWrong(ValidationFailed):
    default_code = "auth.mfa_code_wrong"
    default_title = "The code is not right"


class SecondFactorExpired(Unauthorized):
    default_code = "auth.mfa_expired"
    default_title = "The sign-in waited too long"


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def matching_step(secret: str, code: str, now: datetime, after: int | None) -> int | None:
    """The time step ``code`` belongs to (current ± WINDOW), never one at or before ``after`` (replay)."""
    code = "".join(c for c in code if c.isdigit())
    if len(code) != DIGITS:
        return None
    current = int(now.timestamp()) // STEP
    for step in range(current - WINDOW, current + WINDOW + 1):
        if (after is None or step > after) and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _recovery(code: str) -> str:
    return _hash("".join(code.lower().split()).replace("-", ""))


@dataclass(frozen=True, slots=True)
class Setup:
    secret: str
    uri: str
    qr_svg: str


class MfaService:
    def __init__(self, ctx: IdentityContext, auth: AuthService) -> None:
        self.ctx = ctx
        self.auth = auth

    # --- the secret, kept encrypted ---------------------------------------------------------------------
    def _box(self) -> SecretBox:
        if self.ctx.secret_box is None:
            raise Conflict("Two-step verification needs the application key.", code="auth.mfa_unavailable")
        return self.ctx.secret_box

    def _seal(self, secret: str) -> str:
        return self._box().encrypt(secret, context=CONTEXT)

    def _open(self, sealed: str) -> str:
        return self._box().decrypt(sealed, context=CONTEXT).reveal()

    async def _reauthenticate(
        self, session: AsyncSession, user_id: UUID, password: str, ip: str | None
    ) -> None:
        login = await session.scalar(select(User.login).where(User.id == user_id))
        try:
            checked = await self.auth.verify_credentials(login or "", password, client_ip=ip)
        except InvalidCredentials:
            checked = None
        if checked != user_id:
            raise ValidationFailed("The password is not right.", code="identity.password_current_wrong")

    # --- the member's own -------------------------------------------------------------------------------
    async def enabled(self, user_id: UUID) -> bool:
        async with self.ctx.database.session() as session:
            factor = await session.get(TotpFactor, user_id)
        return factor is not None and factor.confirmed_at is not None

    async def status(self, user_id: UUID) -> dict[str, object]:
        async with self.ctx.database.session() as session:
            factor = await session.get(TotpFactor, user_id)
            left = await session.scalar(
                select(func.count()).where(RecoveryCode.user_id == user_id, RecoveryCode.used_at.is_(None))
            )
        return {
            "enabled": factor is not None and factor.confirmed_at is not None,
            "recovery_codes_left": int(left or 0),
        }

    async def begin(self, principal: Principal, password: str, *, client_ip: str | None) -> Setup:
        """A new secret, not in force until a first code confirms it (``confirm``)."""
        user_id = _own(principal)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await self._reauthenticate(uow.session, user_id, password, client_ip)
            factor = await uow.session.get(TotpFactor, user_id, with_for_update=True)
            if factor is not None and factor.confirmed_at is not None:
                raise Conflict("Two-factor authentication is already on.", code="auth.mfa_already_on")
            secret = new_secret()
            if factor is None:
                uow.session.add(TotpFactor(user_id=user_id, secret=self._seal(secret), created_at=now))
            else:
                factor.secret, factor.created_at, factor.last_step = self._seal(secret), now, None
            login = await uow.session.scalar(select(User.login).where(User.id == user_id))
        issuer = await self._issuer()
        label = quote(f"{issuer}:{login}")
        uri = f"otpauth://totp/{label}?" + urlencode(
            {"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": DIGITS, "period": STEP}
        )
        return Setup(secret, uri, _qr(uri))

    async def confirm(self, principal: Principal, code: str) -> list[str]:
        """The first code from the app turns the second factor on; the recovery codes, shown once."""
        user_id = _own(principal)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            factor = await uow.session.get(TotpFactor, user_id, with_for_update=True)
            if factor is None or factor.confirmed_at is not None:
                raise Conflict("Start the set-up first.", code="auth.mfa_not_started")
            step = matching_step(self._open(factor.secret), code, now, factor.last_step)
            if step is None:
                raise SecondFactorWrong("The code is not right: check your phone's time and try again.")
            factor.confirmed_at, factor.last_step = now, step
            codes = await self._new_codes(uow.session, user_id, now)
            await audit(
                self.ctx,
                uow.session,
                "identity.mfa_enabled",
                principal,
                resource=user_ref(user_id),
                sensitive=True,
            )
            await publish(
                self.ctx,
                uow.session,
                "user.mfa_changed",
                user_id,
                actor=principal,
                occurred_at=now,
                metadata={"by": "on"},
            )
        return codes

    async def disable(self, principal: Principal, password: str, code: str, *, client_ip: str | None) -> None:
        user_id = _own(principal)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await self._reauthenticate(uow.session, user_id, password, client_ip)
            if not await self._accept(uow.session, user_id, code, now):
                raise SecondFactorWrong("The code is not right.")
            await uow.session.execute(delete(TotpFactor).where(TotpFactor.user_id == user_id))
            await uow.session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
            await audit(
                self.ctx,
                uow.session,
                "identity.mfa_disabled",
                principal,
                resource=user_ref(user_id),
                sensitive=True,
            )
            await publish(
                self.ctx,
                uow.session,
                "user.mfa_changed",
                user_id,
                actor=principal,
                occurred_at=now,
                metadata={"by": "off"},
            )

    async def new_recovery_codes(
        self, principal: Principal, password: str, *, client_ip: str | None
    ) -> list[str]:
        user_id = _own(principal)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await self._reauthenticate(uow.session, user_id, password, client_ip)
            factor = await uow.session.get(TotpFactor, user_id)
            if factor is None or factor.confirmed_at is None:
                raise Conflict("Two-factor authentication is off.", code="auth.mfa_off")
            codes = await self._new_codes(uow.session, user_id, now)
            await audit(
                self.ctx,
                uow.session,
                "identity.mfa_recovery_codes",
                principal,
                resource=user_ref(user_id),
                sensitive=True,
            )
        return codes

    async def lift(self, actor: Principal, user_id: UUID, password: str, *, client_ip: str | None) -> None:
        """An administrator turns a member's second factor off (a lost phone and no recovery code left) —
        their own password asked again; never the Admin's (their recovery codes, or the server's console)."""
        own = _own(actor)
        if own == user_id:
            raise Conflict("Turn your own second factor off from your account.", code="auth.mfa_own_account")
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await self._reauthenticate(uow.session, own, password, client_ip)
            if await self.ctx.admin_authority().is_admin(uow.session, user_id):
                raise SoleAdminProtected(
                    "The Admin's second factor is turned off from their own account only."
                )
            await uow.session.execute(delete(TotpFactor).where(TotpFactor.user_id == user_id))
            await uow.session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
            await audit(
                self.ctx,
                uow.session,
                "identity.mfa_lifted",
                actor,
                resource=user_ref(user_id),
                sensitive=True,
            )
            await publish(
                self.ctx,
                uow.session,
                "user.mfa_changed",
                user_id,
                actor=actor,
                occurred_at=now,
                metadata={"by": "admin"},
            )

    # --- the sign-in's second step ----------------------------------------------------------------------
    async def challenge(self, user_id: UUID) -> str:
        """A sign-in waiting for its second factor — refused once the account had ten wrong codes in the last
        quarter of an hour (a password known cannot buy endless tries, one challenge after another)."""
        token = secrets.token_urlsafe(32)
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await uow.session.execute(delete(MfaChallenge).where(MfaChallenge.created_at < now - RECENT))
            wrong = await uow.session.scalar(
                select(func.coalesce(func.sum(MfaChallenge.attempts), 0)).where(
                    MfaChallenge.user_id == user_id
                )
            )
            if int(wrong or 0) >= RECENT_ATTEMPTS:
                raise Throttled("Too many wrong codes: wait a quarter of an hour.")
            uow.session.add(
                MfaChallenge(token_hash=_hash(token), user_id=user_id, attempts=0, created_at=now)
            )
        return token

    async def finish(self, token: str, code: str) -> UUID:
        """The user a challenge was for, once its code (or a recovery code) is right — the challenge is spent
        when it succeeds, ages out, or after five wrong codes."""
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            row = await uow.session.get(MfaChallenge, _hash(token), with_for_update=True)
            if row is None or now - row.created_at > CHALLENGE_TTL or row.attempts >= CHALLENGE_ATTEMPTS:
                raise SecondFactorExpired("Sign in again.")  # kept: its wrong codes still count (RECENT)
            if await self._accept(uow.session, row.user_id, code, now):
                user_id = row.user_id
                await uow.session.delete(row)
                return user_id
            row.attempts += 1
            await audit(
                self.ctx,
                uow.session,
                "auth.mfa_failed",
                None,
                resource=user_ref(row.user_id),
                decision="deny",
                result="failure",
                context={"attempt": row.attempts},
            )
        raise SecondFactorWrong("The code is not right.")

    # --- shared -----------------------------------------------------------------------------------------
    async def _accept(self, session: AsyncSession, user_id: UUID, code: str, now: datetime) -> bool:
        """A current code of the app (once), or an unused recovery code (spent)."""
        factor = await session.get(TotpFactor, user_id, with_for_update=True)
        if factor is None or factor.confirmed_at is None:
            return False
        step = matching_step(self._open(factor.secret), code, now, factor.last_step)
        if step is not None:
            factor.last_step = step
            return True
        spare = await session.scalar(
            select(RecoveryCode)
            .where(
                RecoveryCode.user_id == user_id,
                RecoveryCode.code_hash == _recovery(code),
                RecoveryCode.used_at.is_(None),
            )
            .with_for_update()
        )
        if spare is None:
            return False
        spare.used_at = now
        await audit(
            self.ctx,
            session,
            "auth.mfa_recovery_used",
            Principal(user_id=user_id),
            resource=user_ref(user_id),
            sensitive=True,
        )
        return True

    async def _new_codes(self, session: AsyncSession, user_id: UUID, now: datetime) -> list[str]:
        await session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
        codes = []
        for _ in range(RECOVERY_CODES):
            raw = secrets.token_hex(5)  # 40 bits, shown as xxxxx-xxxxx
            codes.append(f"{raw[:5]}-{raw[5:]}")
            session.add(RecoveryCode(user_id=user_id, code_hash=_recovery(raw), created_at=now))
        return codes

    async def _issuer(self) -> str:
        from portalab.capabilities.i18n import SITE_TERMS

        try:
            terms = self.ctx.capabilities.system_providers(SITE_TERMS)
            name = str(terms[0].provider.terms("en").name) if terms else ""
        except Exception:
            name = ""
        return (name or "Portalab").replace(":", " ")[:60]


def _own(principal: Principal) -> UUID:
    if principal.user_id is None or principal.acting_for is not None:
        raise Unauthorized("Sign in as yourself to change your second factor.")
    return principal.user_id


def _qr(uri: str) -> str:
    import segno

    out = io.BytesIO()
    segno.make(uri, error="m").save(out, kind="svg", scale=5, border=2, dark="#000", light="#fff")
    return out.getvalue().decode("utf-8")
