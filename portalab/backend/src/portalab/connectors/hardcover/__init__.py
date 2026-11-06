"""``hardcover`` connector (issue 362): Hardcover, the community book database — an author's books (the
most read first) and a book series' volumes in order, with their covers and their editions' ISBNs.

* ``media.people``: an author found by name (the same name, folded), their biography, birth, photo and
  books — those they wrote that readers know, merged duplicates, split parts and omnibuses left out.
* ``media.book_series``: the library's books as Hardcover knows them (an edition's ISBN, Hardcover's own
  id, an edition's title by the same author — a translation is one of the book's editions); a series'
  volumes, one per whole position (a split edition's parts are the volumes of some translations); among the
  series of that name, the one holding the library's own volumes, else the one named exactly so.

Hardcover merges a book's duplicates into one (its ``canonical``): a book is always told by that one's id.
* ``service.health_probe``: a one-row read of the catalog.

Its GraphQL API wants a personal token (hardcover.app → Settings → Hardcover API) with the ``read:catalog``
scope alone: the portal reads the public catalog, never a reader's data. Calls are made by the portal only
(the token never reaches a browser); covers are fetched from Hardcover's image host through the portal.
Hardcover's figures (readers, ratings) are told as Hardcover's.
"""

import asyncio
import re
import time
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import BOOK_SERIES, PEOPLE, BookSeries, OwnedBook, PersonCredit, PersonRecord
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding

GRAPHQL = "/v1/graphql"
IMAGE_HOSTS = ("https://assets.hardcover.app",)  # where its covers and photos are served
IMAGE_PATH = re.compile(r"^/(?!.*\.\.)[A-Za-z0-9_./-]{1,110}$")
ISBN = re.compile(r"^[0-9]{9}[0-9X]$|^[0-9]{13}$")
BOOKS = 100  # an author's books in one request (the API's cap for contributions)
KNOWN = 200  # an author's book read by fewer than 1/200 of their most read one's readers: left out
VOLUMES = 500  # a series' entries in one request (every edition of every volume)
LOOKUPS = 50  # the library's books looked up by title in one request
OWNED = 150  # the library's books identified at once
CANDIDATES = 5  # the authors or series of a name looked at
KEPT_SECONDS = 6 * 3600  # a series or a book asked again after that (the API's daily limit)
USER_AGENT = "Portalab (self-hosted media portal; issue 362)"

STATUS = "query Status { authors(limit: 1) { id } }"
SEARCH = """query Search($query: String!, $type: String!, $per: Int!) {
  search(query: $query, query_type: $type, per_page: $per, page: 1) { ids results }
}"""
_BOOK = "id title release_year users_count rating ratings_count image { url }"
_REF = f"{_BOOK} canonical {{ {_BOOK} }}"  # a duplicate's book: the one it was merged into
AUTHOR = f"""query Author($id: Int!) {{
  authors(where: {{id: {{_eq: $id}}}}) {{
    id name slug bio born_date death_date location image {{ url }}
    contributions(
      where: {{
        contributable_type: {{_eq: "Book"}}
        contributor_role: {{slug: {{_eq: "author"}}}}
        book: {{
          canonical_id: {{_is_null: true}}
          is_partial_book: {{_eq: false}}
          compilation: {{_eq: false}}
          users_count: {{_gt: 0}}
        }}
      }}
      order_by: {{book: {{users_count: desc}}}}
      limit: {BOOKS}
    ) {{
      book {{ {_BOOK} }}
    }}
  }}
}}"""
SERIES = f"""query Series($ids: [Int!]!) {{
  series(where: {{id: {{_in: $ids}}, canonical_id: {{_is_null: true}}}}) {{
    id name slug author {{ name }}
    book_series(
      order_by: {{position: asc}}
      where: {{position: {{_is_null: false}}, compilation: {{_eq: false}}}}
      limit: {VOLUMES}
    ) {{
      position featured details
      book {{ {_REF} is_partial_book }}
    }}
  }}
}}"""
BY_ISBN = f"""query ByIsbn($isbns: [String!]!) {{
  editions(where: {{_or: [{{isbn_13: {{_in: $isbns}}}}, {{isbn_10: {{_in: $isbns}}}}]}}, limit: {VOLUMES}) {{
    isbn_13 isbn_10 book {{ {_REF} }}
  }}
}}"""
BY_SLUG = f"""query BySlug($slugs: [String!]!) {{
  books(where: {{slug: {{_in: $slugs}}}}, limit: {VOLUMES}) {{ slug {_REF} }}
}}"""
BY_TITLE = f"""query ByTitle($titles: [editions_bool_exp!]!, $authors: [String!]!) {{
  editions(
    where: {{_or: $titles, book: {{contributions: {{author: {{name: {{_in: $authors}}}}}}}}}}
    order_by: {{users_count: desc}}
    limit: {VOLUMES}
  ) {{
    title book {{ {_REF} contributions(limit: 10) {{ author {{ name }} }} }}
  }}
}}"""

_KEPT: dict[tuple[Any, str], tuple[float, BookSeries | None]] = {}
_OWNED: dict[tuple[Any, str], tuple[float, tuple[PersonCredit, ...]]] = {}


class HardcoverConfig(BaseConfig):
    base_url: str = Field(
        default="https://api.hardcover.app",
        min_length=8,
        max_length=512,
        pattern=r"^https?://[^\s/$.?#].[^\s]*$",
        title="Address",
        description="Leave https://api.hardcover.app unless you use a proxy.",
    )


def fold(text: str) -> str:
    """A name compared whatever its case, accents and punctuation (« Robin Hobb » = « robin hobb »)."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


def image_ref(value: Any) -> str | None:
    """The path of an image on Hardcover's image host (the only host its images are fetched from)."""
    url = value.get("url") if isinstance(value, Mapping) else value
    if not isinstance(url, str):
        return None
    for host in IMAGE_HOSTS:
        if url.startswith(host + "/"):
            path = urlsplit(url).path
            return path if IMAGE_PATH.fullmatch(path) else None
    return None


def isbn(value: Any) -> str | None:
    text = str(value or "").replace("-", "").replace(" ", "").strip().upper()
    return text if ISBN.fullmatch(text) else None


def author_names(names: Iterable[str]) -> list[str]:
    """An author's name as Hardcover writes it, from the library's (« King,Stephen », « Robin_Hobb »)."""
    out: list[str] = []
    for name in names:
        plain = " ".join(str(name).replace("_", " ").split())[:200]
        if "," in plain:
            last, _, first = plain.partition(",")
            plain = f"{first.strip()} {last.strip()}".strip()
        for each in (str(name).strip()[:200], plain):
            if each and each not in out:
                out.append(each)
    return out


def _like(title: str) -> str:
    """A title matched whatever its case, nothing in it read as a wildcard."""
    return re.sub(r"([\\%_])", r"\\\1", title)


def _int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def map_book(book: Any, *, position: Any = None) -> PersonCredit | None:
    """A Hardcover book as a title of an author's (or a series'): told by the id of the book its duplicates
    were merged into (``canonical``) and its readers', its own title (a translation's, in a translated
    series); its readers are its popularity, its rating (out of 5) told out of 10 like a film's."""
    if not isinstance(book, Mapping) or not book.get("id") or not book.get("title"):
        return None
    canonical = book.get("canonical")
    base = canonical if isinstance(canonical, Mapping) and canonical.get("id") else book
    rating = base.get("rating")
    return PersonCredit(
        tmdb_id=str(base["id"]),
        kind="book",
        title=str(book["title"])[:300],
        year=_int(book.get("release_year")) or _int(base.get("release_year")),
        department="writing",
        poster=image_ref(book.get("image")) or image_ref(base.get("image")),
        popularity=float(base.get("users_count") or 0),
        vote_average=round(float(rating) * 2, 1) if isinstance(rating, int | float) and rating else None,
        vote_count=int(base.get("ratings_count") or 0),
        position=float(position) if isinstance(position, int | float) else None,
    )


def map_author(document: Any) -> PersonRecord | None:
    if not isinstance(document, Mapping) or not document.get("id") or not document.get("name"):
        return None
    books = [map_book((c or {}).get("book")) for c in document.get("contributions") or []]
    credits: dict[str, PersonCredit] = {}
    for book in books:
        if book is not None:
            credits.setdefault(book.tmdb_id, book)  # one book once (several contributions)
    # the books readers know (a stray translation, a boxed set read by a handful left out)
    most = max((book.popularity for book in credits.values()), default=0)
    credits = {key: book for key, book in credits.items() if book.popularity * KNOWN >= most}
    bio = str(document.get("bio") or "").strip()
    return PersonRecord(
        ids={"hardcover": str(document["id"])},
        name=str(document["name"])[:200],
        biography=bio[:6000] or None,
        birthday=str(document["born_date"])[:10] if document.get("born_date") else None,
        deathday=str(document["death_date"])[:10] if document.get("death_date") else None,
        place_of_birth=str(document["location"])[:200] if document.get("location") else None,
        known_for="Writing",
        portrait=image_ref(document.get("image")),
        popularity=None,
        credits=tuple(credits.values()),
    )


def _rank(entry: Mapping[str, Any]) -> tuple[bool, bool, bool, int]:
    """Among a volume's editions in a series: the one Hardcover features, a single volume (not « 1-3 »), a
    whole book rather than a split part, the most read."""
    book = entry.get("book") or {}
    position = entry.get("position")
    single = str(entry.get("details") or "").strip() in ("", f"{position:g}" if position is not None else "")
    return (
        bool(entry.get("featured")),
        single,
        not book.get("is_partial_book"),
        int(book.get("users_count") or 0),
    )


def map_series(document: Any) -> BookSeries | None:
    if not isinstance(document, Mapping) or not document.get("id") or not document.get("name"):
        return None
    best: dict[float, Mapping[str, Any]] = {}
    for entry in document.get("book_series") or []:
        position = (entry or {}).get("position")
        if not isinstance(position, int | float) or position < 0 or position != int(position):
            continue  # a short story or a novella between two volumes (« 2.5 »)
        if position not in best or _rank(entry) > _rank(best[position]):
            best[position] = entry
    volumes = [map_book(entry.get("book"), position=position) for position, entry in sorted(best.items())]
    author = document.get("author")
    return BookSeries(
        ids={"hardcover": str(document["id"])},
        name=str(document["name"])[:200],
        author=str(author["name"])[:200] if isinstance(author, Mapping) and author.get("name") else None,
        volumes=tuple(v for v in volumes if v is not None),
    )


def hits(answer: Any) -> list[tuple[str, Mapping[str, Any]]]:
    """A search's results in order — each id (``ids``) with what the search index tells of it (its hit's
    document: name, books count…)."""
    found = (answer or {}).get("search") if isinstance(answer, Mapping) else None
    if not isinstance(found, Mapping):
        return []
    results = found.get("results")
    documents: list[Mapping[str, Any]] = []
    for hit in (results.get("hits") if isinstance(results, Mapping) else None) or []:
        document = hit.get("document") if isinstance(hit, Mapping) else None
        documents.append(document if isinstance(document, Mapping) else {})
    ids = [str(i) for i in found.get("ids") or []]
    out: list[tuple[str, Mapping[str, Any]]] = []
    for index in range(max(len(ids), len(documents))):
        entry = documents[index] if index < len(documents) else {}
        found_id = str(entry.get("id") or (ids[index] if index < len(ids) else ""))
        if found_id.isdigit():
            out.append((found_id, entry))
    return out


class HardcoverConnector(HttpConnector):
    key = "hardcover"
    name = "Hardcover"
    description = "The community book database: an author's books and a series' volumes, with their covers."
    icon = "book-open"
    category = "metadata"
    config_schema: type[BaseModel] = HardcoverConfig
    secret_fields: frozenset[str] = frozenset({"api_key"})
    provides: Sequence[CapabilityBinding] = (binding(PEOPLE), binding(BOOK_SERIES), binding(HEALTH_PROBE))
    status_path = GRAPHQL
    public_path = None

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        token = service.secrets.get("api_key", "").strip()
        token = token[7:].strip() if token.lower().startswith("bearer ") else token  # pasted with its prefix
        return {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}

    async def graphql(
        self, service: ServiceHandle, document: str, variables: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        answer = await self.request(
            service, "POST", GRAPHQL, json_body={"query": document, "variables": dict(variables or {})}
        )
        if not isinstance(answer, Mapping):
            raise InvalidPayload("not a GraphQL answer")
        errors = answer.get("errors")
        if errors:
            text = str(errors).lower()
            if "scope" in text or "token" in text or "authoriz" in text or "permission" in text:
                raise ProviderAuthError("Hardcover refused the token")
            raise InvalidPayload("Hardcover could not answer the query")
        data = answer.get("data")
        if not isinstance(data, Mapping):
            raise InvalidPayload("not a GraphQL answer")
        return data

    async def get_json(self, service: ServiceHandle, path: str, **params: Any) -> Any:
        """The status (the connection test, the health probe): a one-row read of the catalog."""
        return await self.graphql(service, STATUS)

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "authors" not in status:
            raise InvalidPayload("not Hardcover")
        return "Hardcover"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == PEOPLE:
            return _People(self, service)
        if capability == BOOK_SERIES:
            return _Series(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Images:
    def __init__(self) -> None:
        self.hosts = {
            host: ConnectorHttpClient(host, timeout_seconds=15, max_response_bytes=8 * 1024 * 1024, retries=1)
            for host in IMAGE_HOSTS
        }

    async def fetch(self, ref: str) -> bytes:
        if not IMAGE_PATH.fullmatch(ref):
            raise InvalidPayload("unexpected image reference")
        client = self.hosts[IMAGE_HOSTS[0]]
        try:
            response = await client.get(ref, headers={"User-Agent": USER_AGENT})
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code >= 400:
            raise ConnectionError(f"Hardcover's images answered HTTP {response.status_code}")
        return response.content


class _People:
    def __init__(self, connector: HardcoverConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service
        self.images = _Images()

    async def _found(self, name: str) -> str | None:
        """The author of that name (the same name folded), the one with the most books among namesakes."""
        answer = await self.connector.graphql(
            self.service, SEARCH, {"query": name[:200], "type": "author", "per": CANDIDATES}
        )
        wanted = fold(name)
        same = [
            (int(document.get("books_count") or 0), author_id)
            for author_id, document in hits(answer)
            if fold(str(document.get("name") or "")) == wanted
            or any(fold(str(a)) == wanted for a in document.get("alternate_names") or [])
        ]
        return max(same)[1] if same else None

    async def person(self, name: str, ids: Mapping[str, str], language: str) -> PersonRecord | None:
        author_id = str(ids.get("hardcover") or "")
        if not author_id.isdigit():
            author_id = await self._found(name) or ""
        if not author_id:
            return None
        answer = await self.connector.graphql(self.service, AUTHOR, {"id": int(author_id)})
        found = answer.get("authors") or []
        return map_author(found[0]) if found else None

    async def portrait(self, ref: str, size: str) -> bytes:
        return await self.images.fetch(ref)


async def _nothing() -> Mapping[str, Any]:
    return {}


def _signature(book: OwnedBook) -> str:
    ids = sorted(f"{scheme}:{value}" for scheme, values in book.ids.items() for value in values)
    return "|".join([fold(book.title), ",".join(sorted(fold(a) for a in book.authors)), *ids])


class _Series:
    def __init__(self, connector: HardcoverConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service
        self.images = _Images()

    async def identify(self, books: Sequence[OwnedBook]) -> Mapping[str, Sequence[PersonCredit]]:
        """Each of the library's books with the Hardcover books it may be (the likeliest first): an
        edition's ISBN, Hardcover's own id of it (its slug), else an edition's title by one of its authors."""
        now = time.monotonic()
        out: dict[str, tuple[PersonCredit, ...]] = {}
        asked: list[tuple[OwnedBook, tuple[Any, str]]] = []
        for book in list(books)[:OWNED]:
            key = (self.service.service_id, _signature(book))
            kept = _OWNED.get(key)
            if kept is not None and now - kept[0] < KEPT_SECONDS:
                out[book.key] = kept[1]
            else:
                asked.append((book, key))
        if asked:
            found = await self._identify([book for book, _ in asked])
            if len(_OWNED) > 5000:
                _OWNED.clear()
            for book, key in asked:
                _OWNED[key] = (now, tuple(found.get(book.key, ())))
                out[book.key] = _OWNED[key][1]
        return {key: credits for key, credits in out.items() if credits}

    async def _identify(self, books: Sequence[OwnedBook]) -> dict[str, list[PersonCredit]]:
        found: dict[str, list[PersonCredit]] = {}

        def add(key: str, credit: PersonCredit | None) -> None:
            if credit is not None and all(c.tmdb_id != credit.tmdb_id for c in found.get(key, [])):
                found.setdefault(key, []).append(credit)

        by_isbn: dict[str, list[str]] = {}
        by_slug: dict[str, list[str]] = {}
        for book in books:
            for value in book.ids.get("isbn") or ():
                if (number := isbn(value)) is not None:
                    by_isbn.setdefault(number, []).append(book.key)
            for value in book.ids.get("hardcover") or ():
                slug = str(value).strip()[:200]
                if slug:
                    by_slug.setdefault(slug, []).append(book.key)
        isbns, slugs = await asyncio.gather(
            self._ask(BY_ISBN, {"isbns": sorted(by_isbn)}) if by_isbn else _nothing(),
            self._ask(BY_SLUG, {"slugs": sorted(by_slug)}) if by_slug else _nothing(),
        )
        for edition in isbns.get("editions") or []:
            credit = map_book((edition or {}).get("book"))
            for field in ("isbn_13", "isbn_10"):
                for key in by_isbn.get(isbn((edition or {}).get(field)) or "", []):
                    add(key, credit)
        for book in slugs.get("books") or []:
            for key in by_slug.get(str((book or {}).get("slug") or ""), []):
                add(key, map_book(book))
        # a translation, an edition without its ISBN: an edition's title, by one of the book's authors
        rest = [book for book in books if book.key not in found and fold(book.title) and book.authors]
        chunks = [rest[start : start + LOOKUPS] for start in range(0, len(rest), LOOKUPS)]
        answers = await asyncio.gather(
            *(
                self._ask(
                    BY_TITLE,
                    {
                        "titles": [{"title": {"_ilike": _like(book.title[:300])}} for book in chunk],
                        "authors": author_names(name for book in chunk for name in book.authors),
                    },
                )
                for chunk in chunks
            )
        )
        for chunk, answer in zip(chunks, answers, strict=True):
            for edition in answer.get("editions") or []:
                edition = edition or {}
                written = {
                    fold(str(((c or {}).get("author") or {}).get("name") or ""))
                    for c in (edition.get("book") or {}).get("contributions") or []
                }
                for book in chunk:
                    if fold(book.title) == fold(str(edition.get("title") or "")) and written & {
                        fold(name) for name in author_names(book.authors)
                    }:
                        add(book.key, map_book(edition.get("book")))
        return found

    async def _ask(self, document: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.connector.graphql(self.service, document, variables)

    async def series(self, name: str, known: Sequence[str]) -> BookSeries | None:
        key = (self.service.service_id, f"{fold(name)}|{','.join(sorted(known))}")
        kept = _KEPT.get(key)
        if kept is not None and time.monotonic() - kept[0] < KEPT_SECONDS:
            return kept[1]
        found = await self._series(name, known)
        if len(_KEPT) > 500:
            _KEPT.clear()
        _KEPT[key] = (time.monotonic(), found)
        return found

    async def _series(self, name: str, known: Sequence[str]) -> BookSeries | None:
        answer = await self.connector.graphql(
            self.service, SEARCH, {"query": name[:200], "type": "series", "per": CANDIDATES}
        )
        ids = [int(series_id) for series_id, _ in hits(answer)]
        if not ids:
            return None
        found = await self.connector.graphql(self.service, SERIES, {"ids": ids})
        candidates = [s for s in (map_series(d) for d in found.get("series") or []) if s is not None]
        mine = set(known)

        def shared(series: BookSeries) -> int:
            return sum(1 for volume in series.volumes if volume.tmdb_id in mine)

        best = max(candidates, key=shared, default=None)
        if best is not None and shared(best):
            return best  # the series holding the library's own volumes
        # else the one of that very name with the most volumes (namesakes left empty by their readers)
        wanted = fold(name)
        named = [s for s in candidates if fold(s.name) == wanted]
        return max(named, key=lambda s: len(s.volumes), default=None)

    async def cover(self, ref: str, size: str) -> bytes:
        return await self.images.fetch(ref)
