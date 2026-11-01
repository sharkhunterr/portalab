"""#316 — an edition drawn once as an e-mail, the portal showing that very page: 600 pixels wide, tables and
inline styles only (what mail clients keep), cards side by side that wrap by themselves on a phone (no media
query: inline blocks with a largest width), every text escaped. Its template gives the look and the order;
the snapshot gives what it tells; ``t`` its words, in the edition's language."""

from collections.abc import Callable, Mapping, Sequence
from html import escape
from typing import Any

from portalab.capabilities.notifications.layout import (
    FONT,
    FONT_LINK,
    HIGHLIGHT,
    TITLE_FONT,
    Brand,
    mark,
    rarities,
    ring_line,
)
from portalab.modules.news.editions.template import Section, TemplateDefinition

Words = Callable[[str, Mapping[str, Any] | None], str]
WIDTH = 600
PAD = 24
FONTS = {
    "brand": FONT,  # #320: Plus Jakarta Sans where the mail client has it
    "sans": "'Helvetica Neue', Helvetica, Arial, sans-serif",
    "serif": "Georgia, 'Times New Roman', Times, serif",
    "rounded": "'Trebuchet MS', 'Segoe UI', Verdana, sans-serif",
    "mono": "'Courier New', Courier, monospace",
}


def _cut(text: str | None, length: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


class Drawing:
    def __init__(self, template: TemplateDefinition, snapshot: Mapping[str, Any], t: Words) -> None:
        self.tpl = template
        self.snap = snapshot
        self.t = t
        self.p = template.palette
        self.font = FONTS[template.font]
        self.r = template.radius
        self.portal = str(snapshot.get("portal") or "").rstrip("/")
        self.token = str(snapshot.get("token") or "")

    # --- helpers ---------------------------------------------------------------------------------------
    def link(self, route: str | None) -> str:
        if not route:
            return ""
        return route if route.startswith("http") else f"{self.portal}{route}"

    def picture(self, image_id: str | None) -> str | None:
        if not image_id or not self.token:
            return None
        return f"{self.portal}/api/v1/newsletters/pictures/{self.token}/{image_id}"

    def text_style(
        self, size: int, *, weight: int = 400, color: str | None = None, line: float = 1.45
    ) -> str:
        return (
            f"font-family:{self.font};font-size:{size}px;font-weight:{weight};line-height:{line};"
            f"color:{color or self.p.text};margin:0"
        )

    def meta(self, item: Mapping[str, Any]) -> str:
        parts = [str(item["year"])] if item.get("year") else []
        parts += [str(g) for g in (item.get("genres") or [])[:2]]
        if item.get("detail"):
            parts.append(str(item["detail"]))
        if item.get("plays"):
            parts.append(self.t("edition.plays", {"count": int(item["plays"])}))
        return escape(" · ".join(parts))

    def rating(self, item: Mapping[str, Any]) -> str:
        if not item.get("rating"):
            return ""
        return f'<span style="color:{self.p.accent};font-weight:700">★ {float(item["rating"]):.1f}</span>'

    def cover(self, item: Mapping[str, Any], width: int, *, ratio: float = 1.5) -> str:
        source = self.picture(item.get("picture"))
        alt = escape(str(item.get("title") or ""))
        if source:
            image = (
                f'<img src="{escape(source)}" alt="{alt}" width="{width}" style="display:block;width:100%;'
                f"max-width:{width}px;height:auto;border:0;border-radius:{self.r}px;"
                f'background:{self.p.border}">'
            )
        else:  # no picture: its kind, on a tile of the poster's shape
            label = escape(self.kind(item.get("kind")))
            image = (
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="'
                f'border-collapse:separate;background:{self.p.border};border-radius:{self.r}px">'
                f'<tr><td height="{int(width * ratio)}" align="center" valign="middle" style="'
                f'{self.text_style(12, weight=700, color=self.p.muted)}">{label}</td></tr></table>'
            )
        href = self.link(item.get("route"))
        return f'<a href="{escape(href)}" style="text-decoration:none">{image}</a>' if href else image

    def title_link(self, item: Mapping[str, Any], size: int) -> str:
        title = escape(str(item.get("title") or ""))
        href = self.link(item.get("route"))
        style = self.text_style(size, weight=700, line=1.3)
        inner = (
            f'<a href="{escape(href)}" style="color:{self.p.text};text-decoration:none">{title}</a>'
            if href
            else title
        )
        return f'<p style="{style}">{inner}</p>'

    def block(self, inner: str, *, padding: str = f"{PAD}px") -> str:
        """A section's card on the page."""
        return (
            f'<tr><td style="padding:0 0 16px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="border-collapse:separate;background:{self.p.surface};'
            f'border:1px solid {self.p.border};border-radius:{self.r}px"><tr><td style="padding:{padding}">'
            f"{inner}</td></tr></table></td></tr>"
        )

    def heading(self, text: str) -> str:
        return (
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 16px"><tr>'
            f'<td style="border-left:4px solid {self.p.accent};padding:2px 0 2px 10px;'
            f'{self.text_style(18, weight=700, line=1.25)}">{escape(text)}</td></tr></table>'
        )

    # --- the page -------------------------------------------------------------------------------------
    def header(self) -> str:
        site = escape(str(self.snap.get("site") or "Portalab"))
        # the name is over it: the headline alone (the e-mail's subject keeps both)
        title = escape(str(self.snap.get("headline") or self.snap.get("title") or ""))
        period = escape(str(self.snap.get("period_label") or ""))
        tagline = escape(self.tpl.tagline)
        if self.tpl.header == "brand":
            # #320, #322: as the portal's e-mails — its mark and name, a card under the ring's blues
            return (
                f'<tr><td style="padding:0 4px 18px">{mark(Brand(str(self.snap.get("site") or "Portalab")))}'
                "</td></tr>"
                f'<tr><td style="padding:0 0 16px"><table role="presentation" width="100%" cellpadding="0" '
                f'cellspacing="0" style="border-collapse:separate;background:{self.p.surface};'
                f'border:1px solid {self.p.border};border-radius:{self.r}px;overflow:hidden">'
                f"<tr><td>{ring_line()}</td></tr>"
                f'<tr><td style="padding:26px {PAD}px">'
                f'<p style="{self.text_style(12, weight=700, color=HIGHLIGHT)};letter-spacing:1.5px;'
                f'text-transform:uppercase">{rarities()}&nbsp; {period}</p>'
                f'<p style="{self.text_style(28, weight=800, line=1.2)};font-family:{TITLE_FONT};'
                f'margin-top:8px">{title}</p>'
                + (
                    f'<p style="{self.text_style(15, color=self.p.muted)};margin-top:8px">{tagline}</p>'
                    if tagline
                    else ""
                )
                + "</td></tr></table></td></tr>"
            )
        if self.tpl.header == "banner":
            return (
                f'<tr><td style="padding:0 0 16px"><table role="presentation" width="100%" cellpadding="0" '
                f'cellspacing="0" style="border-collapse:separate;background:{self.p.accent};'
                f'border-radius:{self.r}px"><tr><td style="padding:28px {PAD}px">'
                f'<p style="{self.text_style(13, weight=700, color=self.p.accent_text)};letter-spacing:1px;'
                f'text-transform:uppercase;opacity:0.85">{site}</p>'
                f'<p style="{self.text_style(28, weight=800, color=self.p.accent_text, line=1.2)};'
                f'margin-top:6px">{title}</p>'
                f'<p style="{self.text_style(14, color=self.p.accent_text)};margin-top:8px;opacity:0.9">'
                f"{period}{' · ' + tagline if tagline else ''}</p></td></tr></table></td></tr>"
            )
        if self.tpl.header == "centered":
            return (
                f'<tr><td align="center" style="padding:24px 0 24px">'
                f'<p style="{self.text_style(13, weight=700, color=self.p.accent)};letter-spacing:2px;'
                f'text-transform:uppercase">{site}</p>'
                f'<p style="{self.text_style(30, weight=800, line=1.2)};margin-top:8px">{title}</p>'
                f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:14px auto">'
                f'<tr><td width="56" height="4" style="background:{self.p.accent};border-radius:2px;'
                f'font-size:0;line-height:0">&nbsp;</td></tr></table>'
                f'<p style="{self.text_style(14, color=self.p.muted)}">{period}</p>'
                + (f'<p style="{self.text_style(14, color=self.p.muted)}">{tagline}</p>' if tagline else "")
                + "</td></tr>"
            )
        return (
            f'<tr><td style="padding:8px 0 16px;border-bottom:2px solid {self.p.text}">'
            f'<p style="{self.text_style(30, weight=700, line=1.15)}">{title}</p>'
            f'<p style="{self.text_style(13, color=self.p.muted)};margin-top:6px">{site} · {period}'
            f"{' · ' + tagline if tagline else ''}</p></td></tr>"
            f'<tr><td style="height:16px;font-size:0;line-height:0">&nbsp;</td></tr>'
        )

    def notice(self) -> str:
        text = str(self.snap.get("notice") or "").strip()
        if not text:
            return ""
        body = "<br>".join(escape(line) for line in text.splitlines())
        return (
            f'<tr><td style="padding:0 0 16px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="border-collapse:separate;background:{self.p.surface};'
            f"border:1px solid {self.p.border};border-left:4px solid {self.p.accent};"
            f'border-radius:{self.r}px"><tr><td style="padding:16px 20px">'
            f'<p style="{self.text_style(14, weight=700, color=self.p.accent)}">'
            f"{escape(self.t('edition.section.notice', None))}</p>"
            f'<p style="{self.text_style(15)};margin-top:6px">{body}</p></td></tr></table></td></tr>'
        )

    def stats(self) -> str:
        figures = self.snap.get("stats")
        if not figures or not figures.get("plays"):
            return ""
        tiles = [
            ("plays", f"{int(figures['plays']):,}".replace(",", " ")),
            ("hours", f"{round(float(figures.get('seconds') or 0) / 3600):,}".replace(",", " ")),
            ("members", str(figures.get("members") or "—")),
            ("works", str(figures.get("works") or "—")),
        ]
        width = (WIDTH - 2 * PAD - 2) // 4
        cells = "".join(
            f'<div style="display:inline-block;vertical-align:top;width:100%;max-width:{width}px;'
            f'padding:6px 4px;box-sizing:border-box;text-align:center">'
            f'<p style="{self.text_style(26, weight=800, color=self.p.accent, line=1.1)}">{escape(value)}</p>'
            f'<p style="{self.text_style(12, color=self.p.muted)};margin-top:4px">'
            f"{escape(self.t(f'edition.stats.{key}', None))}</p></div>"
            for key, value in tiles
        )
        trend = ""
        before = float((figures.get("previous") or {}).get("seconds") or 0)
        if before > 0:
            change = round((float(figures.get("seconds") or 0) - before) / before * 100)
            trend = (
                f'<p style="{self.text_style(13, color=self.p.muted)};margin-top:12px;text-align:center">'
                f"{escape(self.t('edition.stats.trend', {'change': f'{change:+d} %'}))}</p>"
            )
        kinds = [
            f"{self.kind(k['kind'])} {round(float(k['seconds']) / 3600)} h"
            for k in (figures.get("by_kind") or [])[:5]
            if float(k.get("seconds") or 0) >= 1800
        ]
        by_kind = (
            f'<p style="{self.text_style(13, color=self.p.muted)};margin-top:6px;text-align:center">'
            f"{escape(' · '.join(kinds))}</p>"
            if kinds
            else ""
        )
        return self.block(
            self.heading(self.t("edition.section.stats", None))
            + f'<div style="font-size:0;text-align:center">{cells}</div>{trend}{by_kind}'
        )

    # --- the sections of titles ---------------------------------------------------------------------
    def kind(self, kind: str | None) -> str:
        """A kind's name — a kind the words do not know (a new service's) as it is."""
        word = self.t(f"edition.kind.{kind or 'movie'}", None)
        return str(kind or "") if word.startswith("edition.") else word

    def grid(self, items: Sequence[Mapping[str, Any]], section: Section, *, first: int = 1) -> str:
        inner = WIDTH - 2 * PAD - 2
        width = inner // section.columns
        cells = []
        for rank, item in enumerate(items, start=first):
            badge = (
                f'<span style="display:inline-block;background:{self.p.accent};color:{self.p.accent_text};'
                f'border-radius:999px;padding:1px 8px;font-size:11px;font-weight:700;margin-bottom:4px">'
                f"#{rank}</span><br>"
                if section.kind == "top"
                else ""
            )
            cells.append(
                f'<div style="display:inline-block;vertical-align:top;width:100%;max-width:{width}px;'
                f'padding:6px;box-sizing:border-box;text-align:left">{self.cover(item, width - 12)}'
                f'<div style="padding-top:8px">{badge}{self.title_link(item, 14)}'
                f'<p style="{self.text_style(12, color=self.p.muted, line=1.4)};margin-top:2px">'
                f"{self.meta(item)}</p>"
                + (
                    f'<p style="{self.text_style(12, line=1.4)};margin-top:2px">{self.rating(item)}</p>'
                    if item.get("rating")
                    else ""
                )
                + "</div></div>"
            )
        return f'<div style="font-size:0;margin:0 -6px">{"".join(cells)}</div>'

    def rows(self, items: Sequence[Mapping[str, Any]], section: Section, *, pictures: bool = True) -> str:
        out = []
        for index, item in enumerate(items):
            overview = (
                f'<p style="{self.text_style(13, color=self.p.muted, line=1.5)};margin-top:4px">'
                f"{escape(_cut(item.get('overview') or item.get('summary'), 220))}</p>"
                if section.overview and (item.get("overview") or item.get("summary"))
                else ""
            )
            picture = (
                f'<td width="72" valign="top" style="padding:0 14px 0 0">{self.cover(item, 72)}</td>'
                if pictures
                else ""
            )
            border = f"border-top:1px solid {self.p.border};" if index else ""
            out.append(
                f'<tr><td style="{border}padding:{12 if index else 0}px 0 12px">'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{picture}'
                f'<td valign="top">{self.title_link(item, 15)}'
                f'<p style="{self.text_style(12, color=self.p.muted)};margin-top:2px">{self.meta(item)}'
                f"{' · ' + self.rating(item) if item.get('rating') else ''}</p>{overview}</td></tr></table>"
                "</td></tr>"
            )
        return (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(out)}</table>'
        )

    def hero(self, items: Sequence[Mapping[str, Any]], section: Section) -> str:
        first, rest = items[0], items[1:]
        href = self.link(first.get("route"))
        button = (
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:14px"><tr>'
            f'<td style="background:{self.p.accent};border-radius:{max(self.r, 6)}px">'
            f'<a href="{escape(href)}" style="display:inline-block;padding:10px 18px;'
            f'{self.text_style(14, weight=700, color=self.p.accent_text)};text-decoration:none">'
            f"{escape(self.t('edition.open', None))} →</a></td></tr></table>"
            if href
            else ""
        )
        lead = (
            f'<div style="font-size:0">'
            f'<div style="display:inline-block;vertical-align:top;width:100%;max-width:190px;'
            f'padding:0 18px 12px 0;box-sizing:border-box">{self.cover(first, 172)}</div>'
            f'<div style="display:inline-block;vertical-align:top;width:100%;'
            f'max-width:{WIDTH - 2 * PAD - 194}px">'
            f"{self.title_link(first, 22)}"
            f'<p style="{self.text_style(13, color=self.p.muted)};margin-top:4px">{self.meta(first)}'
            f"{' · ' + self.rating(first) if first.get('rating') else ''}</p>"
            + (
                f'<p style="{self.text_style(14, line=1.55)};margin-top:10px">'
                f"{escape(_cut(first.get('overview') or first.get('summary'), 420))}</p>"
                if section.overview and (first.get("overview") or first.get("summary"))
                else ""
            )
            + f"{button}</div></div>"
        )
        # the headline is the first: the grid goes on from the second
        return lead + (f'<div style="height:12px"></div>{self.grid(rest, section, first=2)}' if rest else "")

    def compact(self, items: Sequence[Mapping[str, Any]]) -> str:
        lines = []
        for item in items:
            title = escape(str(item.get("title") or ""))
            href = self.link(item.get("route"))
            name = (
                f'<a href="{escape(href)}" style="color:{self.p.text};font-weight:700;text-decoration:none">'
                f"{title}</a>"
                if href
                else f"<strong>{title}</strong>"
            )
            when = escape(str(item.get("day") or ""))
            meta = self.meta(item)
            lines.append(
                f'<p style="{self.text_style(14, line=1.5)};padding:5px 0;border-bottom:1px dotted '
                f'{self.p.border}"><span style="color:{self.p.accent}">●</span> {name}'
                f'<span style="color:{self.p.muted}">{" — " + meta if meta else ""}'
                f"{' · ' + when if when else ''}</span></p>"
            )
        return "".join(lines)

    def section(self, section: Section, data: Mapping[str, Any]) -> str:
        if section.kind == "notice":
            return self.notice()
        if section.kind == "stats":
            return self.stats()
        items = list(data.get("items") or [])[: section.limit]
        if not items:
            return ""
        layout = section.layout
        if section.kind == "articles" and layout in ("grid", "hero"):
            layout = "list"  # the news desk's articles have no posters
        if layout == "grid":
            body = self.grid(items, section)
        elif layout == "hero":
            body = self.hero(items, section)
        elif layout == "list":
            body = self.rows(items, section, pictures=section.kind != "articles")
        else:
            body = self.compact(items)
        return self.block(self.heading(str(data.get("title") or "")) + body)

    def footer(self) -> str:
        site = escape(str(self.snap.get("site") or "Portalab"))
        page = self.link(str(self.snap.get("page") or ""))
        unsubscribe = self.link("/settings/notifications#newsletters")
        see = (
            f'<p style="{self.text_style(14, weight=700)}"><a href="{escape(page)}" style="color:'
            f'{self.p.accent};text-decoration:none">{escape(self.t("edition.see", {"site": site}))}</a></p>'
            if page
            else ""
        )
        return (
            f'<tr><td align="center" style="padding:12px 0 8px">{see}'
            f'<p style="{self.text_style(12, color=self.p.muted)};margin-top:8px">'
            f"{escape(self.t('edition.footer', {'site': site, 'date': str(self.snap.get('day') or '')}))}"
            f'<br><a href="{escape(unsubscribe)}" style="color:{self.p.muted}">'
            f"{escape(self.t('edition.unsubscribe', None))}</a></p></td></tr>"
        )

    def html(self) -> str:
        sections = self.snap.get("sections") or []
        body = "".join(
            self.section(section, sections[index] if index < len(sections) else {})
            for index, section in enumerate(self.tpl.sections)
        )
        if not body:
            body = self.block(
                f'<p style="{self.text_style(15, color=self.p.muted)};text-align:center">'
                f"{escape(self.t('edition.empty', None))}</p>"
            )
        scheme = "dark" if self.p.background.lower() < "#808080" else "light"
        language = escape(str(self.snap.get("language") or "en"))
        return (
            f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="{scheme}"><meta name="supported-color-schemes" '
            f'content="{scheme}"><title>{escape(str(self.snap.get("title") or ""))}</title>'
            '<base target="_top">'
            f"{FONT_LINK if self.tpl.font == 'brand' else ''}</head>"
            f'<body style="margin:0;padding:0;background:{self.p.background};-webkit-text-size-adjust:100%">'
            '<div style="display:none;max-height:0;overflow:hidden">'
            f"{escape(str(self.snap.get('preheader') or ''))}"
            "</div>"
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="'
            f'background:{self.p.background}"><tr><td align="center" style="padding:24px 12px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="'
            f'max-width:{WIDTH}px;margin:0 auto">{self.header()}{body}{self.footer()}</table>'
            "</td></tr></table></body></html>"
        )

    def text(self) -> str:
        lines = [str(self.snap.get("title") or ""), str(self.snap.get("period_label") or ""), ""]
        if self.snap.get("notice"):
            lines += [str(self.snap["notice"]), ""]
        figures = self.snap.get("stats")
        if figures and figures.get("plays"):
            hours = round(float(figures.get("seconds") or 0) / 3600)
            lines += [
                f"{self.t('edition.section.stats', None)}: {figures['plays']} "
                f"{self.t('edition.stats.plays', None)} · {hours} {self.t('edition.stats.hours', None)}",
                "",
            ]
        for section in self.snap.get("sections") or []:
            items = section.get("items") or []
            if not items:
                continue
            lines.append(str(section.get("title") or "").upper())
            for item in items:
                meta = " · ".join(str(p) for p in (item.get("year"), item.get("detail")) if p)
                lines.append(
                    f"- {item.get('title')}{' (' + meta + ')' if meta else ''}"
                    f"  {self.link(item.get('route'))}"
                )
            lines.append("")
        if self.snap.get("page"):
            lines.append(self.link(str(self.snap["page"])))
        return "\n".join(lines).strip()


def render(template: TemplateDefinition, snapshot: Mapping[str, Any], t: Words) -> tuple[str, str]:
    """The edition as an e-mail page (HTML) and as plain text."""
    drawing = Drawing(template, snapshot, t)
    return drawing.html(), drawing.text()
