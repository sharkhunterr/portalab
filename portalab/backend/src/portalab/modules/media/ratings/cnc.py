"""Issue 478 — the CNC's film visas, from its open data (data.gouv.fr « Liste des visas d'exploitations
cinématographiques »): each visa's decision tells a film's French classification in full — « Avertissement »
is « tous publics » with a warning (scenes that may upset young viewers), which TMDB's « TP » does not say.

The list (≈ 95,000 visas, a CSV of ≈ 13 MB) is fetched once a week by a job, its feature films kept in
``media.cnc_visas``. A film is matched by its visa number when TMDB's French cinema release names it
(« Visa CNC 142250 »), else by its title (French or original, folded) and year."""

import csv
import io
import re
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from portalab.core import egress
from portalab.core.db import Database
from portalab.modules.media.models import CncVisa
from portalab.modules.media.observability import log

DATASET = "6311c164ebfb165ddc828ded"
API = f"https://www.data.gouv.fr/api/1/datasets/{DATASET}/"
MAX_BYTES = 40 * 1024 * 1024  # the list is ≈ 13 MB: anything far larger is not it
BATCH = 2000
FEATURE = "long-métrage"
VISA_NOTE = re.compile(r"visa\D{0,12}(\d{3,7})", re.IGNORECASE)

egress.EGRESS.allow("www.data.gouv.fr", "cnc visas")  # 030: known hosts of the outbound allow-list
egress.EGRESS.allow("static.data.gouv.fr", "cnc visas")


def fold(title: str) -> str:
    """A title as matched: lower case, no accents, letters and digits only (« Mad Max : Fury road » →
    « madmaxfuryroad »)."""
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)[:200]


def titles_of(cnc_title: str) -> list[str]:
    """The CNC writes a foreign film « French title. Original title »: both are matched."""
    parts = [p.strip() for p in re.split(r"\.\s+(?=[^\s])", cnc_title) if p.strip()]
    return parts or [cnc_title]


def warning(decision: str | None) -> bool:
    return bool(decision) and "avertissement" in str(decision).lower()


def parse(raw: bytes) -> list[dict[str, Any]]:
    """The list's feature films: visa, title, folded title, year, direction, decision (others left out)."""
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = [h.strip().lower() for h in next(reader, [])]

    def column(*names: str) -> int | None:
        for name in names:
            for index, value in enumerate(header):
                if value.startswith(name):
                    return index
        return None

    at = {
        "title": column("titre"),
        "direction": column("réalisation", "realisation"),
        "format": column("format"),
        "year": column("date"),
        "visa": column("n° de visa", "n°", "numéro", "numero"),
        "decision": column("décision", "decision"),
    }
    if at["title"] is None or at["visa"] is None or at["decision"] is None:
        raise ValueError("unexpected CNC list header")
    out: dict[int, dict[str, Any]] = {}

    def cell(row: list[str], field: str) -> str:
        index = at[field]
        return row[index].strip() if index is not None and index < len(row) else ""

    for row in reader:

        def get(field: str, row: list[str] = row) -> str:
            return cell(row, field)

        if at["format"] is not None and get("format").lower() != FEATURE:
            continue
        visa, decision, title = get("visa"), get("decision"), get("title")
        if not visa.isdigit() or not decision or not title:
            continue
        year = get("year")[:4]
        first = titles_of(title)[0]
        out[int(visa)] = {
            "visa": int(visa),
            "title": title[:400],
            "key": fold(first),
            "year": int(year) if year.isdigit() else None,
            "direction": get("direction")[:300] or None,
            "decision": decision[:80],
        }
    return list(out.values())


class CncVisas:
    def __init__(self, database: Database, client: httpx.AsyncClient | None = None) -> None:
        self.database = database
        self.client = client

    async def _get(self, url: str) -> httpx.Response:
        if self.client is not None:
            return await self.client.get(url, timeout=60, follow_redirects=True)
        async with httpx.AsyncClient(timeout=60, event_hooks=egress.hooks(), follow_redirects=True) as client:
            return await client.get(url)

    async def download(self) -> bytes:
        """The list's CSV, as data.gouv.fr serves its latest version."""
        answer = await self._get(API)
        answer.raise_for_status()
        resources = answer.json().get("resources") or []
        url = next(
            (
                str(r["url"])
                for r in resources
                if isinstance(r, dict)
                and str(r.get("format", "")).lower() == "csv"
                and str(r.get("url", "")).startswith("https://static.data.gouv.fr/")
            ),
            None,
        )
        if url is None:
            raise ValueError("no CSV in the CNC's dataset")
        return await self._read(url)

    async def _read(self, url: str) -> bytes:
        """The CSV read as it comes, cut off past ``MAX_BYTES`` (never held whole when far too large)."""

        async def read(client: httpx.AsyncClient) -> bytes:
            chunks: list[bytes] = []
            size = 0
            async with client.stream("GET", url, timeout=120, follow_redirects=True) as answer:
                answer.raise_for_status()
                async for chunk in answer.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("the CNC list is unexpectedly large")
                    chunks.append(chunk)
            return b"".join(chunks)

        if self.client is not None:
            return await read(self.client)
        async with httpx.AsyncClient(timeout=120, event_hooks=egress.hooks()) as client:
            return await read(client)

    async def store(self, visas: Sequence[dict[str, Any]]) -> int:
        """The list replaced as a whole (a visa withdrawn is gone too), in one transaction."""
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(CncVisa))
            for start in range(0, len(visas), BATCH):
                await uow.session.execute(pg_insert(CncVisa).values(list(visas[start : start + BATCH])))
        return len(visas)

    async def refresh(self) -> int:
        try:
            visas = parse(await self.download())
        except (httpx.HTTPError, ValueError) as exc:  # (a host refused by the allow-list too)
            log.info("the CNC's visas were not refreshed", extra={"reason": type(exc).__name__})
            return 0
        if not visas:
            return 0
        return await self.store(visas)

    async def find(
        self, notes: Iterable[str | None], titles: Iterable[str | None], year: int | None
    ) -> CncVisa | None:
        """A film's visa: the number its French cinema release names, else its title and year (±1)."""
        numbers = [int(m.group(1)) for n in notes if n and (m := VISA_NOTE.search(n))]
        keys = [k for t in titles if t and (k := fold(t))]
        async with self.database.session() as session:
            for number in numbers:
                found = await session.get(CncVisa, number)
                if found is not None:
                    return found
            if not keys or year is None:
                return None
            rows = (
                await session.execute(
                    select(CncVisa)
                    .where(CncVisa.key.in_(keys), CncVisa.year.between(year - 1, year + 1))
                    .order_by(CncVisa.visa.desc())
                    .limit(1)
                )
            ).scalars()
            return rows.first()
