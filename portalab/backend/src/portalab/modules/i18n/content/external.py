"""External content (T032; R12, FR-017..019): source text and provenance are kept as received; a
presentation translation, if a ``TranslationProvider`` is configured (none by default), is computed for
display only and never stored over the source. Content without a declared language follows
``i18n.unknownLanguagePolicy`` (``show_as_is`` with a marker, or ``hide``)."""

from dataclasses import dataclass
from typing import Any

from portalab.capabilities.i18n import LocaleContext, TranslationProvider


@dataclass(frozen=True, slots=True)
class Presented:
    text: str
    language: str | None
    source_text: str
    source_language: str | None
    translated: bool
    machine: bool
    hidden: bool
    marker: str | None
    provenance: dict[str, Any]


async def present(
    text: str,
    *,
    declared_language: str | None,
    provenance: dict[str, Any],
    ctx: LocaleContext,
    unknown_policy: str = "show_as_is",
    provider: TranslationProvider | None = None,
    translate: bool = False,
) -> Presented:
    if declared_language is None:
        hidden = unknown_policy == "hide"
        return Presented(
            text if not hidden else "",
            None,
            text,
            None,
            False,
            False,
            hidden,
            "language_unknown",
            dict(provenance),
        )
    if not translate or provider is None or declared_language.split("-")[0] == ctx.language.split("-")[0]:
        return Presented(
            text, declared_language, text, declared_language, False, False, False, None, dict(provenance)
        )
    try:
        translation = await provider.translate(text, declared_language, ctx.language)
    except Exception:
        return Presented(
            text,
            declared_language,
            text,
            declared_language,
            False,
            False,
            False,
            "translation_unavailable",
            dict(provenance),
        )
    return Presented(
        translation.text,
        translation.language,
        text,
        declared_language,
        True,
        translation.machine,
        False,
        "machine_translation" if translation.machine else "translation",
        dict(provenance),
    )
