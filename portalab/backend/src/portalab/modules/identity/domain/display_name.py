"""Display name and login normalization (research R7, FR-001/010/026).

Uniqueness is enforced on a normalized key (NFKC + casefold, inner whitespace collapsed) so case variants and
compatibility homoglyphs (full-width letters, ligatures…) collide. Mixing letters from several scripts is
refused, which blocks the classic Latin/Cyrillic/Greek confusable spoofing.
"""

import re
import unicodedata

from portalab.core.errors import ValidationFailed

DISPLAY_NAME_MIN = 2
DISPLAY_NAME_MAX = 32
LOGIN_MIN = 3
LOGIN_MAX = 64

_ALLOWED_PUNCTUATION = frozenset(" _-.'")
_LOGIN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_SPACES = re.compile(r"\s+")


class InvalidDisplayName(ValidationFailed):
    default_code = "user.display_name_invalid"
    default_title = "Invalid display name"


class InvalidLogin(ValidationFailed):
    default_code = "user.login_invalid"
    default_title = "Invalid login"


def _script(char: str) -> str | None:
    if not char.isalpha():
        return None
    name = unicodedata.name(char, "")
    return name.split(" ", 1)[0] if name else "UNKNOWN"


def clean_display_name(raw: str) -> str:
    """Validated display name as shown (NFKC, trimmed, single inner spaces)."""
    value = _SPACES.sub(" ", unicodedata.normalize("NFKC", raw)).strip()
    if not DISPLAY_NAME_MIN <= len(value) <= DISPLAY_NAME_MAX:
        raise InvalidDisplayName(
            f"A display name has {DISPLAY_NAME_MIN} to {DISPLAY_NAME_MAX} characters.",
            extensions={"reason": "length"},
        )
    for char in value:
        if not (char.isalnum() or char in _ALLOWED_PUNCTUATION):
            raise InvalidDisplayName(
                "Use letters, digits, spaces and _ - . ' only.", extensions={"reason": "characters"}
            )
    if not any(char.isalnum() for char in value):
        raise InvalidDisplayName(
            "A display name needs at least one letter or digit.", extensions={"reason": "empty"}
        )
    scripts = {script for char in value if (script := _script(char))}
    if len(scripts) > 1:
        raise InvalidDisplayName(
            "Do not mix alphabets in a display name.", extensions={"reason": "mixed_scripts"}
        )
    return value


def display_name_key(raw: str) -> str:
    """Uniqueness key of a (valid) display name."""
    return unicodedata.normalize("NFKC", clean_display_name(raw).casefold())


def normalize_login(raw: str) -> str:
    """Login used for sign-in and uniqueness: NFKC + casefold, restricted alphabet."""
    value = unicodedata.normalize("NFKC", raw).strip().casefold()
    if not LOGIN_MIN <= len(value) <= LOGIN_MAX or not _LOGIN.fullmatch(value):
        raise InvalidLogin(
            f"A login has {LOGIN_MIN} to {LOGIN_MAX} characters: letters a-z, digits, '.', '_' or '-'.",
        )
    return value


def login_lookup_key(raw: str) -> str | None:
    """Normalized login for a sign-in attempt, or ``None`` if it cannot be a valid login (never raises)."""
    try:
        return normalize_login(raw)
    except InvalidLogin:
        return None
