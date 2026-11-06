"""``hardcover`` connector (issue 362): Hardcover, the community book database — an author's books (the
most read first) and a book series' volumes in order, with their covers and their editions' ISBNs.

* ``media.people``: an author found by name (the same name, folded), their biography, birth, photo and
  books — those they wrote, merged duplicates and partial books left out.
* ``media.book_series``: a series' volumes, one per position; among the series of that name, the one
  holding the library's own volumes (their ISBNs), else the one named exactly so.
* ``service.health_probe``: a one-row read of the catalog.

Its GraphQL API wants a personal token (hardcover.app → Settings → Hardcover API) with the ``read:catalog``
scope alone: the portal reads the public catalog, never a reader's data. Calls are made by the portal only
(the token never reaches a browser); covers are fetched from Hardcover's image host through the portal.
Hardcover's figures (readers, ratings) are told as Hardcover's.
"""

import re
import time
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import BOOK_SERIES, PEOPLE, BookSeries, PersonCredit, PersonRecord
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding

GRAPHQL = "/v1/graphql"
IMAGE_HOSTS = ("https://assets.hardcover.app",)  # where its covers and photos are served
IMAGE_PATH = re.compile(r"^/(?!.*\.\.)[A-Za-z0-9_./-]{1,110}$")
ISBN = re.compile(r"^[0-9]{9}[0-9X]$|^[0-9]{13}$")
BOOKS = 100  # an author's books in one request (the API's cap for contributions)
EDITIONS = 25  # each book's editions read for their ISBNs
CANDIDATES = 5  # the authors or series of a name looked at
KEPT_SECONDS = 6 * 3600  # a series asked again after that (the API's daily limit)
USER_AGENT = "Portalab (self-hosted media portal; issue 362)"

STATUS = "query Status { authors(limit: 1) { id } }"
SEARCH = """query Search($query: String!, $type: String!, $per: Int!) {
  search(query: $query, query_type: $type, per_page: $per, page: 1) { ids results }
}"""
_BOOK = f"""id title release_year users_count rating ratings_count image {{ url }}
  editions(where: {{isbn_13: {{_is_null: false}}}}, order_by: {{users_count: desc}}, limit: {EDITIONS}) {{
    isbn_13 isbn_10
  }}"""
AUTHOR = f"""query Author($id: Int!) {{
  authors(where: {{id: {{_eq: $id}}}}) {{
    id name slug bio born_date death_date location image {{ url }}
    contributions(
      where: {{
        contributable_type: {{_eq: "Book"}}
        contributor_role: {{slug: {{_eq: "author"}}}}
        book: {{canonical_id: {{_is_null: true}}, is_partial_book: {{_eq: false}}}}
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
      distinct_on: position
      order_by: [{{position: asc}}, {{book: {{users_count: desc}}}}]
      where: {{
        book: {{canonical_id: {{_is_null: true}}, is_partial_book: {{_eq: false}}}}
        compilation: {{_eq: false}}
      }}
    ) {{
      position
      book {{ {_BOOK} }}
    }}
  }}
}}"""

_KEPT: dict[tuple[Any, str], tuple[float, BookSeries | None]] = {}


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


def _isbns(book: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    for edition in book.get("editions") or []:
        for field in ("isbn_13", "isbn_10"):
            value = str((edition or {}).get(field) or "").replace("-", "").strip().upper()
            if ISBN.fullmatch(value) and value not in found:
                found.append(value)
    return found


def _int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def map_book(book: Any, *, position: Any = None) -> PersonCredit | None:
    """A Hardcover book as a title of an author's (or a series'): its readers are its popularity, its
    rating (out of 5) told out of 10 like a film's."""
    if not isinstance(book, Mapping) or not book.get("id") or not book.get("title"):
        return None
    rating = book.get("rating")
    return PersonCredit(
        tmdb_id=str(book["id"]),
        kind="book",
        title=str(book["title"])[:300],
        year=_int(book.get("release_year")),
        department="writing",
        poster=image_ref(book.get("image")),
        popularity=float(book.get("users_count") or 0),
        vote_average=round(float(rating) * 2, 1) if isinstance(rating, int | float) and rating else None,
        vote_count=int(book.get("ratings_count") or 0),
        isbns=tuple(_isbns(book)),
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


def map_series(document: Any) -> BookSeries | None:
    if not isinstance(document, Mapping) or not document.get("id") or not document.get("name"):
        return None
    volumes = [
        map_book((entry or {}).get("book"), position=(entry or {}).get("position"))
        for entry in document.get("book_series") or []
    ]
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


class _Series:
    def __init__(self, connector: HardcoverConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service
        self.images = _Images()

    async def series(self, name: str, isbns: Sequence[str]) -> BookSeries | None:
        key = (self.service.service_id, f"{fold(name)}|{','.join(sorted(isbns))}")
        kept = _KEPT.get(key)
        if kept is not None and time.monotonic() - kept[0] < KEPT_SECONDS:
            return kept[1]
        found = await self._series(name, isbns)
        if len(_KEPT) > 500:
            _KEPT.clear()
        _KEPT[key] = (time.monotonic(), found)
        return found

    async def _series(self, name: str, isbns: Sequence[str]) -> BookSeries | None:
        answer = await self.connector.graphql(
            self.service, SEARCH, {"query": name[:200], "type": "series", "per": CANDIDATES}
        )
        ids = [int(series_id) for series_id, _ in hits(answer)]
        if not ids:
            return None
        found = await self.connector.graphql(self.service, SERIES, {"ids": ids})
        candidates = [s for s in (map_series(d) for d in found.get("series") or []) if s is not None]
        mine = {isbn.replace("-", "").upper() for isbn in isbns}

        def shared(series: BookSeries) -> int:
            return sum(1 for volume in series.volumes if mine & set(volume.isbns))

        best = max(candidates, key=shared, default=None)
        if best is not None and shared(best):
            return best  # the series holding the library's own volumes
        wanted = fold(name)
        return next((s for s in candidates if fold(s.name) == wanted), None)

    async def cover(self, ref: str, size: str) -> bytes:
        return await self.images.fetch(ref)
