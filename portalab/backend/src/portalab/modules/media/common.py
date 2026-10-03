"""Small shared helpers: title normalization (matching, sorting), strong-id normalization, payload hashing
and sanitization (no credentials or query strings ever stored from a source)."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from portalab.capabilities.media import ID_SCHEMES

_ARTICLES = re.compile(r"^(the|a|an|le|la|les|l'|un|une|der|die|das|el|los|las)\s+")
_PUNCT = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().casefold()
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def sort_title(title: str) -> str:
    return _ARTICLES.sub("", normalize_title(title))[:500] or normalize_title(title)[:500]


def strong_ids(ids: Mapping[str, str]) -> dict[str, str]:
    """Known schemes only (``tmdb``, ``imdb``…), trimmed; values never contain spaces."""
    out: dict[str, str] = {}
    for scheme, value in ids.items():
        key = str(scheme).strip().lower()
        text = str(value).strip()
        if key in ID_SCHEMES and text and len(text) <= 200 and " " not in text:
            out[key] = text
    return out


def payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def safe_ref(ref: str | None) -> str | None:
    """An opaque image ref, or a URL stripped of user info, query and fragment (tokens never stored)."""
    if not ref:
        return None
    if "://" not in ref:
        return ref if "?" not in ref and "@" not in ref else ref.split("?", 1)[0].split("@")[-1]
    parts = urlsplit(ref)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname}{port}{parts.path}"[:300]
