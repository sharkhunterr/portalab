"""#320 — every e-mail the portal sends wears Portalab's look: the default theme's night palette (the brand's
reference: ``portalab-dark``), the site's name beside its mark, a card under the accent-to-amber line, a clear
action button, Plus Jakarta Sans where the mail client has it (a safe font otherwise). Tables and inline
styles only — what mail clients keep —, every text escaped."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html import escape
from typing import Any

from portalab.capabilities.i18n import SITE_TERMS

# portalab-dark (frontend/src/design-system/themes/builtin): the brand's palette
NIGHT = "#0b0e17"
CARD = "#161b2b"
BORDER = "#2b3349"
TEXT = "#eef1f8"
SOFT = "#c9cfdd"
MUTED = "#a9b2c7"
ACCENT = "#7f9cff"
ON_ACCENT = "#0b0e17"
AMBER = "#ffb547"
VIOLET = "#c48dff"
FONT = "'Plus Jakarta Sans', 'Segoe UI', Helvetica, Arial, sans-serif"
FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800'
    '&display=swap" rel="stylesheet">'
)
GRADIENT = f"linear-gradient(90deg, {ACCENT}, {VIOLET} 55%, {AMBER})"
URL = re.compile(r"(https?://[^\s<]+)")


@dataclass(frozen=True, slots=True)
class Brand:
    """Who sends: the site's name, and its public address (the links' and pictures' base)."""

    name: str = "Portalab"
    portal: str = ""

    def link(self, route: str | None) -> str:
        if not route:
            return ""
        return route if route.startswith(("http://", "https://")) else f"{self.portal.rstrip('/')}{route}"


async def site_brand(provider: Callable[[str], Any | None], portal: str, language: str) -> Brand:
    """The site's own name (the one its catalogs say instead of « Portalab »), and its public address."""
    terms = provider(SITE_TERMS)
    name = None
    if terms is not None:
        try:
            await terms.refresh()
            name = terms.terms(language).name
        except Exception:
            name = None
    return Brand(name=name or "Portalab", portal=portal)


def _style(size: int, *, weight: int = 400, color: str = TEXT, line: float = 1.55) -> str:
    return (
        f"font-family:{FONT};font-size:{size}px;font-weight:{weight};line-height:{line};"
        f"color:{color};margin:0"
    )


def paragraphs(text: str) -> str:
    """Plain text as paragraphs: blank lines part them, line breaks stay, addresses become links."""
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        safe = escape(block).replace("\n", "<br>")
        safe = URL.sub(
            lambda m: (
                f'<a href="{m.group(1)}" style="color:{ACCENT};text-decoration:underline">{m.group(1)}</a>'
            ),
            safe,
        )
        out.append(f'<p style="{_style(15, color=SOFT)};margin:0 0 14px">{safe}</p>')
    return "".join(out)


def button(label: str, href: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0 4px"><tr>'
        f'<td bgcolor="{ACCENT}" style="background:{ACCENT};border-radius:999px">'
        f'<a href="{escape(href)}" style="display:inline-block;padding:12px 24px;'
        f"{_style(15, weight=700, color=ON_ACCENT)};"
        f'text-decoration:none;border-radius:999px">{escape(label)} →</a></td></tr></table>'
    )


def items_list(items: Sequence[str]) -> str:
    rows = "".join(
        f'<tr><td width="18" valign="top" style="padding:9px 0;color:{ACCENT};font-size:14px">●</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid {BORDER};{_style(15, color=TEXT)}">'
        f"{escape(item)}</td></tr>"
        for item in items
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'


def code(value: str) -> str:
    return (
        f'<p style="margin:18px 0;padding:14px 18px;background:{NIGHT};border:1px solid {BORDER};'
        f"border-radius:12px;font-family:'SFMono-Regular', Consolas, monospace;font-size:20px;"
        f'letter-spacing:2px;color:{AMBER};text-align:center">{escape(value)}</p>'
    )


def mark(brand: Brand) -> str:
    """The site's mark: its initial on the brand's gradient (a plain accent where gradients are not drawn)."""
    initial = escape((brand.name.strip() or "P")[0].upper())
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="36" height="36" align="center" valign="middle" bgcolor="{ACCENT}" style="'
        f"width:36px;height:36px;border-radius:10px;background:{ACCENT};background-image:{GRADIENT};"
        f'{_style(18, weight=800, color=ON_ACCENT, line=1)}">{initial}</td>'
        f'<td style="padding-left:12px;{_style(17, weight=800, color=TEXT, line=1.2)}">'
        f"{escape(brand.name)}</td>"
        "</tr></table>"
    )


def dress(
    brand: Brand,
    *,
    title: str,
    body_html: str,
    kicker: str | None = None,
    note: str | None = None,
    manage: tuple[str, str] | None = None,
    language: str = "en",
    preheader: str | None = None,
) -> str:
    """An e-mail page in Portalab's look around ``body_html`` (already safe markup)."""
    head = (
        f'<p style="{_style(12, weight=700, color=ACCENT)};letter-spacing:1.5px;text-transform:uppercase;'
        f'margin:0 0 8px">{escape(kicker)}</p>'
        if kicker
        else ""
    )
    footer = []
    if note:
        footer.append(escape(note))
    if manage:
        footer.append(
            f'<a href="{escape(manage[1])}" style="color:{ACCENT};text-decoration:none;font-weight:600">'
            f"{escape(manage[0])}</a>"
        )
    return (
        f'<!doctype html><html lang="{escape(language)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">'
        f"<title>{escape(title)}</title>{FONT_LINK}</head>"
        f'<body style="margin:0;padding:0;background:{NIGHT};-webkit-text-size-adjust:100%">'
        f'<div style="display:none;max-height:0;overflow:hidden">{escape(preheader or title)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{NIGHT}" '
        f'style="background:{NIGHT}"><tr><td align="center" style="padding:28px 12px 36px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px">'
        f'<tr><td style="padding:0 4px 18px">{mark(brand)}</td></tr>'
        f'<tr><td bgcolor="{CARD}" style="background:{CARD};border:1px solid {BORDER};border-radius:18px;'
        f'overflow:hidden">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td height="4" bgcolor="{ACCENT}" style="height:4px;line-height:4px;font-size:0;'
        f'background:{ACCENT};background-image:{GRADIENT}">&nbsp;</td></tr>'
        f'<tr><td style="padding:28px 28px 26px;{_style(15, color=SOFT)}">{head}'
        f'<h1 style="{_style(24, weight=800, color=TEXT, line=1.25)};margin:0 0 16px">{escape(title)}</h1>'
        f"{body_html}</td></tr></table></td></tr>"
        f'<tr><td align="center" style="padding:20px 16px 0;{_style(12, color=MUTED, line=1.7)}">'
        f"{'<br>'.join(footer)}</td></tr>"
        "</table></td></tr></table></body></html>"
    )
