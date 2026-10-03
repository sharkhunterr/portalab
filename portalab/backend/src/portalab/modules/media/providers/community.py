"""Community context (T031; for 012): a Media object referenced from a post shows a **public summary**
(title, kind, year, availability) — never who watched it; references to merged objects resolve to the
survivor and unknown references reveal nothing."""

from typing import Any

from portalab.core.authz_port import Principal
from portalab.modules.media.catalog import CatalogPort


async def public_summary(port: CatalogPort, ref: str, viewer: Principal) -> dict[str, Any] | None:
    found = await port.resolve_ref(ref, viewer)
    if found is None:
        return None
    return {
        "id": str(found.id),
        "kind": found.kind,
        "title": found.title,
        "year": found.year,
        "available": found.available,
        "route": found.route,
    }
