"""Model output hygiene (T022): answers are plain text with light markdown — markdown images (exfiltration
beacons) become their alt text, raw HTML is stripped, links keep only ``http(s)`` or in-portal targets,
known secret values are masked. The UI also renders answers as text, never as HTML."""

import re
from collections.abc import Iterable

from portalab.modules.ai.redaction import mask_secrets

IMAGE = re.compile(r"!\[([^\]]{0,200})\]\([^)]*\)")
TAG = re.compile(r"<\/?[a-zA-Z][^>]{0,500}>")
LINK = re.compile(r"\[([^\]]{0,200})\]\(([^)\s]*)[^)]*\)")


def _link(match: re.Match[str]) -> str:
    label, target = match.group(1), match.group(2)
    if target.startswith(("https://", "http://")) or (target.startswith("/") and not target.startswith("//")):
        return match.group(0)
    return label


def sanitize_answer(text: str, secrets: Iterable[str | None] = ()) -> str:
    text = IMAGE.sub(lambda m: m.group(1), text)
    text = TAG.sub("", text)
    text = LINK.sub(_link, text)
    return mask_secrets(text, secrets)
