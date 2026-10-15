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

from portalab.modules.ui.visuals.manifest import ManifestError, parse_pack
from portalab.modules.ui.visuals.store import MAX_BYTES, PackageError

ADDRESS = re.compile(
    r"^https://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?"
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
    if ref and "/" in ref and not folder:  # « tree/main/packs/x »: the first part is the ref
        ref, _, folder = ref.partition("/")
    return Repository(match["owner"], match["repo"], ref, folder)


class GitHub:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def _get(self, url: str, *, accept: str = "application/json") -> httpx.Response:
        headers = {"Accept": accept, "User-Agent": "portalab-visual-packs"}
        if self.client is not None:
            return await self.client.get(url, headers=headers, follow_redirects=True)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            return await client.get(url, headers=headers, follow_redirects=True)

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
        response = await self._get(url, accept="application/zip")
        if response.status_code >= 400:
            raise GitHubError(f"GitHub answered {response.status_code} for the archive at {ref}")
        if len(response.content) > MAX_BYTES:
            raise PackageError("the archive is too large")
        return response.content
