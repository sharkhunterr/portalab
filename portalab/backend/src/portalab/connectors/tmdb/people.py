"""#92 — a TMDB person (biography, birth, every title of theirs) as a ``PersonRecord``; shared by the TMDB
connector and by Seerr, which serves TMDB's people camel-cased (``snake`` turns them back)."""

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from portalab.capabilities.media import PersonCredit, PersonRecord

IMAGE_PATH = re.compile(r"^/[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png|svg)$")
_CAMEL = re.compile(r"(?<=[a-z0-9])([A-Z])")


def image_ref(path: Any) -> str | None:
    return path if isinstance(path, str) and IMAGE_PATH.fullmatch(path) else None


def same_name(value: Any) -> str:
    """A name compared without case, accents or punctuation (« Chris O'Dowd » is « chris o dowd »)."""
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    spaced = re.sub(r"[^\w]+", " ", bare)
    return " ".join(spaced.encode("ascii", "ignore").decode().casefold().split())


def snake(value: Any) -> Any:
    """``placeOfBirth`` → ``place_of_birth``, through nested documents and lists."""
    if isinstance(value, Mapping):
        return {_CAMEL.sub(r"_\1", str(k)).lower(): snake(v) for k, v in value.items()}
    if isinstance(value, list):
        return [snake(v) for v in value]
    return value


def _year(value: Any) -> int | None:
    text = str(value or "")
    return int(text[:4]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None


def map_person(document: Mapping[str, Any]) -> PersonRecord:
    """#92: a TMDB person (with ``combined_credits`` and ``external_ids``) as a record — one entry per title
    and department (a director who also wrote it shows once in each)."""
    external = document.get("external_ids") or {}
    ids = {"tmdb": str(document["id"])}
    if external.get("imdb_id"):
        ids["imdb"] = str(external["imdb_id"])[:20]
    combined = document.get("combined_credits") or {}
    credits: dict[tuple[str, str, str], PersonCredit] = {}
    for entry in [*(combined.get("cast") or []), *(combined.get("crew") or [])]:
        if (
            not isinstance(entry, Mapping)
            or entry.get("media_type") not in ("movie", "tv")
            or not entry.get("id")
        ):
            continue
        kind: Any = "movie" if entry["media_type"] == "movie" else "series"
        title = entry.get("title") or entry.get("name")
        if not title:
            continue
        department = str(entry.get("department") or "cast").lower()[:40] if "job" in entry else "cast"
        if (
            kind == "series"
            and department == "cast"
            and entry.get("character") in (None, "")
            and (entry.get("episode_count") or 0) <= 1
        ):
            continue  # a single talk-show appearance is not a role
        key = (kind, str(entry["id"]), department)
        role = entry.get("character") if department == "cast" else entry.get("job")
        if key in credits:
            if role and credits[key].role and role not in str(credits[key].role):
                known = credits[key]
                credits[key] = PersonCredit(**{**_fields(known), "role": f"{known.role}, {role}"[:200]})
            continue
        credits[key] = PersonCredit(
            tmdb_id=str(entry["id"]),
            kind=kind,
            title=str(title)[:300],
            year=_year(entry.get("release_date") or entry.get("first_air_date")),
            role=str(role)[:200] if role else None,
            department=department,
            poster=image_ref(entry.get("poster_path")),
            popularity=float(entry.get("popularity") or 0),
            vote_average=float(entry["vote_average"]) if entry.get("vote_average") else None,
            vote_count=int(entry.get("vote_count") or 0),
        )
    return PersonRecord(
        ids=ids,
        name=str(document.get("name") or "")[:200],
        biography=(str(document.get("biography") or "")[:6000]) or None,
        birthday=document.get("birthday") or None,
        deathday=document.get("deathday") or None,
        place_of_birth=(str(document.get("place_of_birth") or "")[:200]) or None,
        known_for=(str(document.get("known_for_department") or "")[:40]) or None,
        portrait=image_ref(document.get("profile_path")),
        popularity=float(document["popularity"]) if document.get("popularity") else None,
        also_known_as=[str(a)[:120] for a in document.get("also_known_as") or [] if a][:8],
        credits=list(credits.values()),
    )


def _fields(credit: PersonCredit) -> dict[str, Any]:
    return {name: getattr(credit, name) for name in PersonCredit.__slots__}
