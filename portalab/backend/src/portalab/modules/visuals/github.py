"""A pack on GitHub: ``https://github.com/<owner>/<repo>`` (optionally ``/tree/<ref>/<folder>``).

The version on offer is the latest release's tag when the repository has releases, its default branch
otherwise (or the ``ref`` the address names); its ``pack.json`` there says the pack's version, compared with
the installed one — an update is proposed, never applied on its own. Only GitHub's own hosts are reached,
with short timeouts and the pack's size limit.
"""

import re
from dataclasses import dataclass
from typing import Any

import httpx

from portalab.modules.visuals.manifest import ManifestError, parse_pack
from portalab.modules.visuals.store import MAX_BYTES, PackageError

ADDRESS = re.compile(
    r"^https://github\.com/(?P<owner>[\w-]+)/(?P<repo>[\w.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<ref>[\w./-]+?)(?:/(?P<folder>[\w./-]+))?)?/?$"
)
TIMEOUT = httpx.Timeout(20.0, connect=10.0)


@dataclass(frozen=True, slots=True)
class Repository:
    owner: str
    repo: str
    ref: str | None = None
    folder: str = ""

    @property
    def url(self) -> str:
        tail = f"/tree/{self.ref}" + (f"/{self.folder}" if self.folder else "") if self.ref else ""
        return f"https://github.com/{self.owner}/{self.repo}{tail}"


@dataclass(frozen=True, slots=True)
class Offer:
    """What the repository offers now: the ref it was read at and the pack's id and version there."""

    ref: str
    pack: str
    version: str
    release: bool


class GitHubError(ValueError):
    pass


def parse_address(url: str) -> Repository:
    match = ADDRESS.match(url.strip())
    if not match:
        raise GitHubError("a GitHub address is https://github.com/<owner>/<repository>[/tree/<ref>/<folder>]")
    ref = match["ref"]
    folder = (match["folder"] or "").strip("/")
    if ".." in (ref or "").split("/") or ".." in folder.split("/") or match["repo"] in (".", ".."):
        raise GitHubError("a GitHub address never leaves its repository")
    if ref and "/" in ref and not folder:  # « tree/main/packs/x »: the first part is the ref
        ref, _, folder = ref.partition("/")
    return Repository(match["owner"], match["repo"], ref, folder)


HOSTS = frozenset({"github.com", "api.github.com", "raw.githubusercontent.com", "codeload.github.com"})
MAX_REDIRECTS = 5
MAX_JSON_BYTES = 1024 * 1024


class GitHub:
    """GitHub's own hosts only: every redirect checked (never followed elsewhere), every answer read as a
    stream and cut at its limit (an archive larger than a pack may be is never held whole)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def _fetch(self, client: httpx.AsyncClient, url: str, accept: str, limit: int) -> tuple[int, bytes]:
        headers = {"Accept": accept, "User-Agent": "portalab-visual-packs"}
        for _ in range(MAX_REDIRECTS + 1):
            target = httpx.URL(url)
            if target.scheme != "https" or target.host not in HOSTS:
                raise GitHubError(f"refused to reach {target.host or url!r}: not one of GitHub's hosts")
            async with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
                if response.is_redirect:
                    url = str(target.join(response.headers.get("location", "")))
                    continue
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise PackageError("the answer is too large")
                return response.status_code, bytes(body)
        raise GitHubError("too many redirects")

    async def _get(
        self, url: str, *, accept: str = "application/json", limit: int = MAX_JSON_BYTES
    ) -> httpx.Response:
        if self.client is not None:
            status, body = await self._fetch(self.client, url, accept, limit)
        else:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                status, body = await self._fetch(client, url, accept, limit)
        return httpx.Response(status, content=body)

    async def _json(self, url: str) -> Any:
        response = await self._get(url)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise GitHubError(f"GitHub answered {response.status_code} for {url}")
        return response.json()

    async def offer(self, repository: Repository) -> Offer:
        base = f"https://api.github.com/repos/{repository.owner}/{repository.repo}"
        ref = repository.ref
        release = False
        if ref is None:
            latest = await self._json(f"{base}/releases/latest")
            if latest and latest.get("tag_name"):
                ref, release = str(latest["tag_name"]), True
            else:
                info = await self._json(base)
                if not info:
                    raise GitHubError("this repository does not exist or is private")
                ref = str(info.get("default_branch") or "main")
        folder = f"{repository.folder}/" if repository.folder else ""
        raw = await self._get(
            f"https://raw.githubusercontent.com/{repository.owner}/{repository.repo}/{ref}/{folder}pack.json",
            accept="application/json, text/plain",
        )
        if raw.status_code >= 400:
            raise GitHubError(f"no pack.json at {ref}/{folder or ''}")
        try:
            pack = parse_pack(raw.content)
        except ManifestError as error:
            raise GitHubError(str(error)) from error
        return Offer(ref, pack.id, pack.version, release)

    async def download(self, repository: Repository, ref: str) -> bytes:
        url = f"https://codeload.github.com/{repository.owner}/{repository.repo}/zip/{ref}"
        response = await self._get(url, accept="application/zip", limit=MAX_BYTES)
        if response.status_code >= 400:
            raise GitHubError(f"GitHub answered {response.status_code} for the archive at {ref}")
        return response.content
