"""#316 — an edition's template: its **look** (palette, font, corners, header) and its **sections** (what
each tells, how — a grid of posters, a list, a headline then a grid, compact lines —, how many titles, of
which kinds), in their order. Data only (never code nor markup): the news desk writes its own, the
built-in ones are drawn from it the same way."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Color = Field(pattern=r"^#[0-9a-fA-F]{6}$")
SectionKind = Literal[
    "notice", "stats", "top", "additions", "requests", "releases", "tv", "upcoming", "articles"
]  # #323: « requests » (the period's requests) and « tv » (the series' episodes airing)
Layout = Literal["grid", "list", "hero", "compact"]
MediaGroup = Literal["movie", "series", "book", "audiobook", "game", "album"]  # #323: audiobooks apart
Font = Literal["brand", "sans", "serif", "rounded", "mono"]  # #320: « brand », Plus Jakarta Sans
Header = Literal["brand", "banner", "centered", "minimal"]  # #320: « brand », as the portal's e-mails
TITLED = ("top", "additions", "requests", "releases", "tv", "upcoming", "articles")  # they list titles


class Palette(BaseModel):
    model_config = ConfigDict(extra="forbid")
    background: str = Color
    surface: str = Color
    text: str = Color
    muted: str = Color
    accent: str = Color
    accent_text: str = Color
    border: str = Color


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: SectionKind
    layout: Layout = "grid"
    columns: int = Field(default=3, ge=2, le=4)
    limit: int = Field(default=8, ge=1, le=24)
    media: list[MediaGroup] = Field(default_factory=list, max_length=6)  # empty: every kind
    title: str | None = Field(default=None, max_length=80)  # else its kind's (and media's) own
    overview: bool = True  # the titles' overviews, where the display has room


class TemplateDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=240)
    palette: Palette
    font: Font = "sans"
    radius: int = Field(default=12, ge=0, le=24)
    header: Header = "banner"
    brand: str = Field(default="", max_length=60)  # the name over the title; else the channel's
    tagline: str = Field(default="", max_length=160)
    sections: list[Section] = Field(min_length=1, max_length=12)


# #320: the portal's own night palette (portalab-dark), as its e-mails
PORTALAB = Palette(
    background="#0b0e17",
    surface="#161b2b",
    text="#eef1f8",
    muted="#a9b2c7",
    accent="#7f9cff",
    accent_text="#0b0e17",
    border="#2b3349",
)
LIGHT = Palette(
    background="#f4f5f7",
    surface="#ffffff",
    text="#16181d",
    muted="#6b7280",
    accent="#4f46e5",
    accent_text="#ffffff",
    border="#e5e7eb",
)
NIGHT = Palette(
    background="#0f1220",
    surface="#191d2e",
    text="#f3f4f8",
    muted="#a0a6bd",
    accent="#f5b544",
    accent_text="#191d2e",
    border="#2a3048",
)
PAPER = Palette(
    background="#f6f1e7",
    surface="#fffdf8",
    text="#2b2620",
    muted="#7a6f62",
    accent="#b4472b",
    accent_text="#fffdf8",
    border="#e4dccb",
)

# the built-in templates: Ghostarr's newsletter (posters in a grid), a night magazine, a newspaper of lines
BUILTIN: dict[str, TemplateDefinition] = {
    # #320: the default — Portalab's look, the one of its e-mails
    "portalab": TemplateDefinition(
        name="Portalab",
        description="L'allure du portail : nuit, accent bleu et ambre, les affiches à l'honneur.",
        palette=PORTALAB,
        font="brand",
        radius=16,
        header="brand",
        sections=[
            Section(kind="notice"),
            Section(kind="stats"),
            Section(kind="top", layout="hero", columns=3, limit=4),
            Section(kind="additions", media=["movie"], layout="grid", columns=3, limit=6),
            Section(kind="additions", media=["series"], layout="grid", columns=3, limit=6),
            Section(kind="additions", media=["book", "game", "album"], layout="list", limit=6),
            Section(kind="upcoming", layout="compact", limit=8),
            Section(kind="articles", layout="list", limit=3),
        ],
    ),
    "classic": TemplateDefinition(
        name="Classique",
        description="Les chiffres de la période puis les ajouts en grilles d'affiches, type par type.",
        palette=LIGHT,
        header="banner",
        sections=[
            Section(kind="notice"),
            Section(kind="stats"),
            Section(kind="additions", media=["movie"], layout="grid", columns=3, limit=9),
            Section(kind="additions", media=["series"], layout="grid", columns=3, limit=9),
            Section(kind="additions", media=["book"], layout="grid", columns=4, limit=8),
            Section(kind="additions", media=["game", "album"], layout="list", limit=6),
            Section(kind="top", layout="list", limit=5),
            Section(kind="upcoming", layout="compact", limit=10),
        ],
    ),
    "midnight": TemplateDefinition(
        name="Minuit",
        description="Un magazine sombre : le plus regardé à la une, puis les nouveautés en grandes cartes.",
        palette=NIGHT,
        font="rounded",
        radius=16,
        header="centered",
        sections=[
            Section(kind="notice"),
            Section(kind="top", layout="hero", columns=3, limit=4),
            Section(kind="stats"),
            Section(kind="additions", layout="hero", columns=3, limit=10),
            Section(kind="releases", layout="grid", columns=4, limit=8),
            Section(kind="articles", layout="list", limit=4),
        ],
    ),
    "gazette": TemplateDefinition(
        name="Gazette",
        description="Un journal sobre, en lignes : tout se lit d'un coup d'œil, même sans images.",
        palette=PAPER,
        font="serif",
        radius=0,
        header="minimal",
        sections=[
            Section(kind="notice"),
            Section(kind="stats"),
            Section(kind="additions", layout="compact", limit=20),
            Section(kind="releases", layout="compact", limit=12),
            Section(kind="upcoming", layout="compact", limit=12),
            Section(kind="articles", layout="compact", limit=6),
        ],
    ),
}


# --- #323: what an edition tells, as options ---------------------------------------------------------------
Content = Literal[
    "notice",
    "stats",
    "top",
    "movies",
    "series",
    "books",
    "audiobooks",
    "games",
    "music",
    "requests",
    "releases",
    "tv",
    "upcoming",
    "articles",
]
CONTENTS: tuple[Content, ...] = (
    "notice",
    "stats",
    "top",
    "movies",
    "series",
    "books",
    "audiobooks",
    "games",
    "music",
    "requests",
    "releases",
    "tv",
    "upcoming",
    "articles",
)
DEFAULT_CONTENTS: tuple[Content, ...] = (
    "notice",
    "stats",
    "top",
    "movies",
    "series",
    "books",
    "audiobooks",
    "games",
    "requests",
    "tv",
    "upcoming",
)
# each content: the kind of section it is, and of which kinds of titles
ADDITIONS: dict[str, MediaGroup] = {
    "movies": "movie",
    "series": "series",
    "books": "book",
    "audiobooks": "audiobook",
    "games": "game",
    "music": "album",
}
NOT_SERIES: list[MediaGroup] = [
    "movie",
    "book",
    "audiobook",
    "game",
    "album",
]  # « coming soon » beside the TV


def compose(template: TemplateDefinition, contents: list[str] | tuple[str, ...]) -> TemplateDefinition:
    """The template's look with the contents asked, in their order: each takes the template's own section for
    it (its display, number, title) when it has one, else a section in the template's manner."""
    own = template.sections
    titled = [s for s in own if s.kind in ("additions", "top", "releases", "requests")]
    manner = titled[0] if titled else Section(kind="additions")

    def found(kind: str, group: str | None = None) -> Section | None:
        for section in own:
            if section.kind != kind:
                continue
            if group is None or not section.media or group in section.media:
                return section
        return None

    sections: list[Section] = []
    for content in CONTENTS:
        if content not in contents:
            continue
        if content in ADDITIONS:
            group = ADDITIONS[content]
            base = found("additions", group)
            sections.append(
                (base or manner).model_copy(
                    update={
                        "kind": "additions",
                        "media": [group],
                        "title": base.title if base and base.media == [group] else None,
                    }
                )
            )
        elif content == "upcoming":
            base = found("upcoming")
            media = NOT_SERIES if "tv" in contents else []
            sections.append(
                (base or Section(kind="upcoming", layout="compact", limit=10)).model_copy(
                    update={"media": media}
                )
            )
        elif content == "tv":
            base = found("tv")
            sections.append(base or Section(kind="tv", layout="compact", limit=12, media=["series"]))
        elif content in ("notice", "stats"):
            sections.append(found(content) or Section(kind=content))
        else:
            base = found(content)
            default = manner.model_copy(update={"kind": content, "media": [], "title": None})
            if content == "articles":
                default = Section(kind="articles", layout="list", limit=4)
            sections.append(base or default)
    return template.model_copy(update={"sections": sections or own})


# --- #324: the statistics' charts, as options ---------------------------------------------------------------
Chart = Literal["figures", "activity", "kinds", "weekdays", "hours", "genres"]
CHARTS: tuple[Chart, ...] = ("figures", "activity", "kinds", "weekdays", "hours", "genres")
DEFAULT_CHARTS: tuple[Chart, ...] = ("figures", "activity", "kinds")
