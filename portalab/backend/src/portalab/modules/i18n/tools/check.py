"""Catalog tooling (T010; R7): ICU validity, placeholder & plural-argument parity with the source
language, missing/unused keys, bundle hashes and pseudo-localization (``en-XA`` longer accented text,
``ar-XB`` right-to-left) — ``portalab i18n check|extract|pseudo``."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from portalab.modules.i18n.render.icu import MessageSyntaxError, arguments_of, parse

SOURCE = "en"
_ACCENTS = str.maketrans("aeiouyAEIOUYcnCN", "àéîöüýÀÉÎÖÜÝçñÇÑ")


def load(locales: Path) -> dict[str, dict[str, dict[str, str]]]:
    catalogs: dict[str, dict[str, dict[str, str]]] = {}
    for path in sorted(locales.glob("*/*.json")):
        catalogs.setdefault(path.parent.name, {})[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return catalogs


def check(locales: Path) -> list[str]:
    problems: list[str] = []
    catalogs = load(locales)
    source = catalogs.get(SOURCE, {})
    for language, namespaces in catalogs.items():
        for namespace, messages in namespaces.items():
            reference = source.get(namespace, {})
            for key, message in messages.items():
                try:
                    names = arguments_of(parse(message))
                except MessageSyntaxError as exc:
                    problems.append(f"{language}/{namespace}:{key}: invalid ICU message ({exc})")
                    continue
                if language != SOURCE:
                    if key not in reference:
                        problems.append(f"{language}/{namespace}:{key}: unused (not in {SOURCE})")
                        continue
                    expected = arguments_of(parse(reference[key]))
                    if names != expected:
                        where = f"{language}/{namespace}:{key}"
                        detail = f"placeholders {sorted(names)} != {SOURCE} {sorted(expected)}"
                        problems.append(f"{where}: {detail}")
            if language != SOURCE:
                for key in sorted(set(reference) - set(messages)):
                    problems.append(f"{language}/{namespace}:{key}: missing translation")
    return problems


def bundle_hash(messages: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def _pseudo_text(text: str, rtl: bool) -> str:
    # transform only literal text: arguments, selectors and ICU syntax stay intact
    out, depth, i = [], 0, 0
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0 and c not in "{}":
            out.append(c.translate(_ACCENTS) if not rtl else c)
        else:
            out.append(c)
        i += 1
    body = "".join(out)
    return f"\u202e{body}\u202c" if rtl else f"[{body} ~~~]"


def pseudo(locales: Path, code: str = "en-XA") -> dict[str, dict[str, str]]:
    rtl = code.endswith("XB")
    source = load(locales).get(SOURCE, {})
    return {ns: {k: _pseudo_text(v, rtl) for k, v in msgs.items()} for ns, msgs in source.items()}


def extract(sources: list[Path]) -> dict[str, set[str]]:
    """Keys used in code: ``t("key", namespace="ns")`` (Python) and ``t("ns:key")`` (frontend)."""
    pattern = re.compile(r"""\bt\(\s*["']([a-zA-Z0-9_.-]+):([a-zA-Z0-9_.-]+)["']""")
    found: dict[str, set[str]] = {}
    for root in sources:
        for path in root.rglob("*"):
            if path.suffix not in (".py", ".ts", ".tsx"):
                continue
            for namespace, key in pattern.findall(path.read_text(encoding="utf-8", errors="ignore")):
                found.setdefault(namespace, set()).add(key)
    return found


def report(locales: Path) -> dict[str, Any]:
    catalogs = load(locales)
    return {
        "problems": check(locales),
        "hashes": {f"{lang}/{ns}": bundle_hash(m) for lang, nss in catalogs.items() for ns, m in nss.items()},
    }
