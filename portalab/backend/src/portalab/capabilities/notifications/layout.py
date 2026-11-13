"""#320 — every e-mail the portal sends wears Portalab's look: the default theme's night palette (the brand's
reference: ``portalab-dark``), the site's name beside its mark, a card under the line of the ring's blues, a
clear action button, Plus Jakarta Sans titles and Inter text where the mail client has them (safe fonts
otherwise). Tables and inline styles only — what mail clients keep —, every text escaped.

#322: drawn without CSS gradients nor images (Gmail drops the former, and the latter need the portal reachable
from the internet): the brand's icon told with cells — the portal ring in its blues, the rarities' points —
and the ring's gradient as a line of stepped cells."""

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
HIGHLIGHT = "#a3b8ff"  # the ring's light end (the theme's focus)
DEEP = "#3a55d0"  # the ring's deep end (the light theme's accent)
AMBER = "#ffb547"  # the rarities, on the icon's ring: legendary, rare, epic
RARE = "#5cb4ff"
VIOLET = "#c48dff"
RING = (HIGHLIGHT, ACCENT, DEEP)
TITLE_FONT = "'Plus Jakarta Sans', 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONT = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800'
    '&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">'
)
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


def _style(
    size: int, *, weight: int = 400, color: str = TEXT, line: float = 1.55, title: bool = False
) -> str:
    return (
        f"font-family:{TITLE_FONT if title else FONT};font-size:{size}px;font-weight:{weight};"
        f"line-height:{line};color:{color};margin:0"
    )


def mix(a: str, b: str, share: float) -> str:
    one = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    two = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * share):02x}" for x, y in zip(one, two, strict=True))


def ring_line(steps: int = 24, height: int = 4, colors: Sequence[str] = RING) -> str:
    """The ring's gradient as a line of stepped cells — a gradient every mail client draws."""
    cells = []
    for index in range(steps):
        at = index / (steps - 1) * (len(colors) - 1)
        low = min(int(at), len(colors) - 2)
        color = mix(colors[low], colors[low + 1], at - low)
        cells.append(
            f'<td height="{height}" bgcolor="{color}" style="height:{height}px;line-height:{height}px;'
            f'font-size:0;background:{color}">&nbsp;</td>'
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse"><tr>{"".join(cells)}</tr></table>'
    )


def rarities() -> str:
    """The icon's points — legendary, rare, epic — before a line."""
    return "".join(
        f'<span style="color:{color};font-size:10px;letter-spacing:2px">●</span>'
        for color in (AMBER, RARE, VIOLET)
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
        f"{_style(15, weight=700, color=ON_ACCENT, title=True)};"
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


def excerpt(text: str, limit: int = 500) -> str:
    """Issue 398: someone's words for a notification — their first lines in whole words, the rest in the
    portal."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def facts(rows: Sequence[tuple[str, str]]) -> str:
    """Issue 398: what a notification is about, as label / value lines (a price, a level, a severity…)."""
    if not rows:
        return ""
    lines = "".join(
        f'<tr><td valign="top" style="padding:9px 14px 9px 0;border-bottom:1px solid {BORDER};'
        f'{_style(13, color=MUTED)};white-space:nowrap">{escape(label)}</td>'
        f'<td valign="top" style="padding:9px 0;border-bottom:1px solid {BORDER};'
        f'{_style(15, weight=600, color=TEXT)}">{escape(value)}</td></tr>'
        for label, value in rows
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0 16px">'
        f"{lines}</table>"
    )


def chips(items: Sequence[str]) -> str:
    """Issue 398: what was won, as the interface shows it (« +120 XP », « +15 Coins »)."""
    if not items:
        return ""
    cells = "".join(
        f'<td style="padding:0 8px 8px 0"><span style="display:inline-block;padding:6px 12px;'
        f"border-radius:999px;background:{NIGHT};border:1px solid {BORDER};"
        f'{_style(14, weight=700, color=AMBER)}">{escape(item)}</span></td>'
        for item in items
    )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:2px 0 12px">'
        f"<tr>{cells}</tr></table>"
    )


def quote(text: str) -> str:
    """Issue 398: words someone wrote (a reply, a comment, a note) — set apart, escaped, and with no link
    made from them: an address a member typed never becomes a button in the portal's own e-mail."""
    if not text.strip():
        return ""
    safe = escape(text.strip()).replace("\n", "<br>")
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0 16px">'
        f'<tr><td width="3" bgcolor="{ACCENT}" style="background:{ACCENT};border-radius:3px;font-size:0">'
        f'&nbsp;</td><td style="padding:10px 16px;background:{NIGHT};{_style(15, color=SOFT)}">{safe}</td>'
        "</tr></table>"
    )


def code(value: str) -> str:
    return (
        f'<p style="margin:18px 0;padding:14px 18px;background:{NIGHT};border:1px solid {BORDER};'
        f"border-radius:12px;font-family:'SFMono-Regular', Consolas, monospace;font-size:20px;"
        f'letter-spacing:2px;color:{AMBER};text-align:center">{escape(value)}</p>'
    )


def mark(brand: Brand) -> str:
    """The brand's icon told with cells: the portal ring in its blue on the night tile, its amber point —
    then the site's name."""
    ring = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" align="center"><tr>'
        f'<td width="14" height="14" style="width:14px;height:14px;border:3px solid {ACCENT};'
        f'border-top-color:{HIGHLIGHT};border-bottom-color:{DEEP};border-radius:50%;font-size:0;line-height:0">'
        "&nbsp;</td></tr></table>"
    )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="40" height="40" align="center" valign="middle" bgcolor="{CARD}" style="width:40px;'
        f'height:40px;border-radius:12px;background:{CARD};border:1px solid {BORDER}">{ring}</td>'
        f'<td valign="top" style="padding:2px 0 0 0;color:{AMBER};font-size:9px;line-height:9px">●</td>'
        f'<td style="padding-left:10px;{_style(18, weight=800, color=TEXT, line=1.2, title=True)}">'
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
        f'<p style="{_style(12, weight=700, color=HIGHLIGHT)};letter-spacing:1.5px;text-transform:uppercase;'
        f'margin:0 0 10px">{rarities()}&nbsp; {escape(kicker)}</p>'
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
        f"<tr><td>{ring_line()}</td></tr>"
        f'<tr><td style="padding:28px 28px 26px;{_style(15, color=SOFT)}">{head}'
        f'<h1 style="{_style(24, weight=800, color=TEXT, line=1.25, title=True)};margin:0 0 16px">'
        f"{escape(title)}</h1>"
        f"{body_html}</td></tr></table></td></tr>"
        f'<tr><td align="center" style="padding:20px 16px 0;{_style(12, color=MUTED, line=1.7)}">'
        f"{'<br>'.join(footer)}</td></tr>"
        "</table></td></tr></table></body></html>"
    )
