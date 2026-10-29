"""The site's identity (issue 159): its name instead of « Portalab » (the header, the sign-in page, the tab's
title, the home-screen manifest, the e-mails and notifications through the catalogs), a short name, a
slogan, a logo and an icon; its currency instead of « Coins » — full name in the singular and the plural per
language, a short name, an icon. Empty: Portalab's own; « restore » empties it all.

The catalogs ask :meth:`SiteIdentityService.terms` in every process (capability ``i18n.site_terms``); a
process that did not make the change reads it again within :data:`TTL` seconds. A theme's own words (027
vocabulary) still win for the member who wears it: the member's universe before the site's default.
The administration's technical texts keep « Portalab » (they name the software)."""

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from portalab.capabilities.i18n import SiteTerms
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.core.uploads import UnsafeUpload, reencode_image, square_icon
from portalab.modules.ui.models import SiteIdentity

DEFAULT_NAME = "Portalab"
TTL = 30.0
MAX_IMAGE_BYTES = 2 * 1024 * 1024
# words that go into the catalogs' messages: no ICU syntax, no markup, no control character
WORD = re.compile(r"^[^{}<>#\"\\\x00-\x1f\x7f]+$")
LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
ICON = re.compile(r"^[a-z0-9-]{1,32}$")
LIMITS = {"name": 40, "short_name": 12, "currency_short": 8, "currency": 30, "tagline": 160}
IMAGES = ("logo", "icon")


class InvalidSiteIdentity(ValidationFailed):
    default_code = "ui.site_identity_invalid"
    default_title = "Invalid site identity"


@dataclass(frozen=True, slots=True)
class Identity:
    name: str | None = None
    short_name: str | None = None
    tagline: dict[str, str] = field(default_factory=dict)
    currency: dict[str, dict[str, str]] = field(default_factory=dict)
    currency_short: str | None = None
    currency_icon: str | None = None
    logo_type: str | None = None
    icon_type: str | None = None
    version: int = 0


def _word(value: object, what: str, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) > limit or not WORD.match(text):
        raise InvalidSiteIdentity(
            f'« {what} » holds at most {limit} characters, without {{ }} < > # " or \\.',
            extensions={"field": what},
        )
    return text


def _languages(value: object, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    if len(value) > 12 or not all(isinstance(k, str) and LANGUAGE.match(k) for k in value):
        raise InvalidSiteIdentity(f"« {what} »: one entry per language code.", extensions={"field": what})
    return value


def clean(body: dict[str, Any]) -> dict[str, Any]:
    """The administrator's values, checked and trimmed (an empty value: Portalab's own)."""
    tagline = {}
    for language, text in _languages(body.get("tagline"), "tagline").items():
        line = " ".join(str(text or "").split())
        if line:
            if len(line) > LIMITS["tagline"] or "<" in line or ">" in line:
                raise InvalidSiteIdentity(
                    "The slogan holds at most 160 characters, without < >.", extensions={"field": "tagline"}
                )
            tagline[language] = line
    currency = {}
    for language, names in _languages(body.get("currency"), "currency").items():
        names = names if isinstance(names, dict) else {}
        one = _word(names.get("one"), "currency", LIMITS["currency"])
        other = _word(names.get("other"), "currency", LIMITS["currency"])
        if one or other:
            currency[language] = {"one": one or other or "", "other": other or one or ""}
    icon = body.get("currency_icon") or None
    if icon is not None and not ICON.match(str(icon)):
        raise InvalidSiteIdentity("Unknown icon.", extensions={"field": "currency_icon"})
    return {
        "name": _word(body.get("name"), "name", LIMITS["name"]),
        "short_name": _word(body.get("short_name"), "short_name", LIMITS["short_name"]),
        "tagline": tagline,
        "currency": currency,
        "currency_short": _word(body.get("currency_short"), "currency_short", LIMITS["currency_short"]),
        "currency_icon": icon,
    }


def _pick(per_language: dict[str, Any], language: str) -> Any | None:
    """The language's own, then its base language's, then English's, then the first one written (the names
    are mostly proper nouns: one written in French still names the site in English)."""
    for candidate in (language, language.split("-")[0], "en"):
        if candidate in per_language:
            return per_language[candidate]
    return next(iter(per_language.values()), None)


class SiteIdentityService:
    def __init__(self, database: Database, audit: AuditSink, *, clock: Clock | None = None) -> None:
        self.database = database
        self.audit = audit
        self.clock = clock
        self.identity = Identity()
        self._read_at = 0.0
        self._lock = asyncio.Lock()

    # --- i18n.site_terms ------------------------------------------------------------------------------
    @property
    def version(self) -> int:
        return self.identity.version

    def terms(self, language: str) -> SiteTerms:
        names = _pick(self.identity.currency, language) or {}
        return SiteTerms(
            name=self.identity.name, currency_one=names.get("one"), currency_other=names.get("other")
        )

    async def refresh(self, *, force: bool = False) -> Identity:
        if not force and time.monotonic() - self._read_at < TTL:
            return self.identity
        async with self._lock:
            if force or time.monotonic() - self._read_at >= TTL:
                async with self.database.session() as session:
                    row = await session.get(SiteIdentity, 1)
                self.identity = self._of(row)
                self._read_at = time.monotonic()
        return self.identity

    @staticmethod
    def _of(row: SiteIdentity | None) -> Identity:
        if row is None:
            return Identity()
        return Identity(
            name=row.name,
            short_name=row.short_name,
            tagline=dict(row.tagline or {}),
            currency={k: dict(v) for k, v in (row.currency or {}).items()},
            currency_short=row.currency_short,
            currency_icon=row.currency_icon,
            logo_type=row.logo_type if row.logo else None,
            icon_type=row.icon_type if row.icon else None,
            version=row.version,
        )

    # --- reading --------------------------------------------------------------------------------------
    async def public(self) -> dict[str, Any]:
        """What the sign-in page and the shell show (public: it is on the sign-in page anyway)."""
        identity = await self.refresh()
        name = identity.name or DEFAULT_NAME
        version = identity.version
        return {
            "name": name,
            "short_name": identity.short_name or (name if len(name) <= 12 else name[:12]),
            "custom": identity.name is not None,
            "tagline": identity.tagline,
            "currency": identity.currency,
            "currency_short": identity.currency_short,
            "currency_icon": identity.currency_icon,
            "logo": f"/api/v1/auth/site/logo?v={version}" if identity.logo_type else None,
            "icon": f"/api/v1/auth/site/icon?v={version}" if identity.icon_type else None,
            "version": version,
        }

    async def admin(self) -> dict[str, Any]:
        identity = await self.refresh(force=True)
        return {
            **await self.public(),
            "name": identity.name,
            "short_name": identity.short_name,
            "default_name": DEFAULT_NAME,
        }

    async def image(self, which: str) -> tuple[bytes, str] | None:
        async with self.database.session() as session:
            row = await session.get(SiteIdentity, 1)
        if row is None:
            return None
        data, kind = (row.logo, row.logo_type) if which == "logo" else (row.icon, row.icon_type)
        return (data, kind or "image/png") if data else None

    # --- changing -------------------------------------------------------------------------------------
    async def update(self, actor: Principal, body: dict[str, Any]) -> dict[str, Any]:
        values = clean(body)
        await self._write(actor, "ui.site_identity.updated", values, changed=sorted(values))
        return await self.admin()

    async def set_image(self, actor: Principal, which: str, data: bytes) -> dict[str, Any]:
        if which not in IMAGES:
            raise InvalidSiteIdentity("Unknown image.", extensions={"field": which})
        if not data:
            raise InvalidSiteIdentity("The image is empty.", extensions={"field": which, "reason": "empty"})
        if len(data) > MAX_IMAGE_BYTES:
            raise InvalidSiteIdentity(
                "The image is larger than 2 MiB.", extensions={"field": which, "reason": "too_large"}
            )
        try:
            if which == "icon":
                cleaned, kind = await asyncio.to_thread(square_icon, data), "image/png"
            else:
                cleaned, kind = await asyncio.to_thread(reencode_image, data, max_side=512)
        except UnsafeUpload as exc:
            raise InvalidSiteIdentity(
                "The image cannot be read (PNG, JPEG, WebP or GIF).",
                extensions={"field": which, "reason": exc.reason},
            ) from exc
        await self._write(actor, f"ui.site_identity.{which}_set", {which: cleaned, f"{which}_type": kind})
        return await self.admin()

    async def remove_image(self, actor: Principal, which: str) -> dict[str, Any]:
        if which not in IMAGES:
            raise InvalidSiteIdentity("Unknown image.", extensions={"field": which})
        await self._write(actor, f"ui.site_identity.{which}_removed", {which: None, f"{which}_type": None})
        return await self.admin()

    async def reset(self, actor: Principal) -> dict[str, Any]:
        """Portalab's own name, slogan, images and currency back."""
        values: dict[str, Any] = {
            "name": None,
            "short_name": None,
            "tagline": {},
            "currency": {},
            "currency_short": None,
            "currency_icon": None,
            "logo": None,
            "logo_type": None,
            "icon": None,
            "icon_type": None,
        }
        await self._write(actor, "ui.site_identity.reset", values)
        return await self.admin()

    async def _write(
        self, actor: Principal, action: str, values: dict[str, Any], *, changed: list[str] | None = None
    ) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.scalar(select(SiteIdentity).where(SiteIdentity.id == 1).with_for_update())
            if row is None:
                row = SiteIdentity(id=1, tagline={}, currency={}, version=0, updated_at=now)
                uow.session.add(row)
            for key, value in values.items():
                setattr(row, key, value)
            row.version = (row.version or 0) + 1
            row.updated_at = now
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action=action,
                    actor=actor,
                    resource=ResourceRef("site_identity", "site"),
                    decision="allow",
                    result="success",
                    context={"version": row.version, "fields": changed or sorted(values)},
                    sensitive=False,
                ),
            )
        await self.refresh(force=True)
