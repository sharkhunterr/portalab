"""Source attribution (T021; FR-012..014): every source retrieved this turn gets a number; the answer may
cite ``[n]`` only for those — invalid markers are dropped, so no invented source is ever shown. Sources
keep their class (``real`` with ``as_of``, ``historical``, ``knowledge``); partial / stale / unavailable
tool results become caveats; an answer citing nothing is labelled as interpretation."""

import re
from dataclasses import dataclass, field
from typing import Any

from portalab.capabilities.ai import SourceRef, ToolResult

MARKER = re.compile(r"\[(\d{1,3})\]")
CAVEAT_STATES = ("partial", "stale", "unavailable", "error")


def source_dict(number: int, source: SourceRef) -> dict[str, Any]:
    return {
        "n": number,
        "kind": source.kind,
        "ref": source.ref,
        "title": source.title[:200],
        "class": source.source_class,
        "as_of": source.as_of.isoformat() if source.as_of else None,
        "url": source.url,
        "image": source.image if source.image and source.image.startswith("/api/v1/") else None,
        "detail": source.detail[:120] if source.detail else None,
    }


@dataclass
class Attributor:
    sources: list[SourceRef] = field(default_factory=list)
    caveats: list[dict[str, str]] = field(default_factory=list)

    def add(self, tool: str, result: ToolResult) -> list[dict[str, Any]]:
        """Numbers the new sources of a tool result; returns them (already-seen sources keep their number)."""
        if result.state in CAVEAT_STATES:
            caveat = {"tool": tool, "state": result.state}
            if caveat not in self.caveats:
                self.caveats.append(caveat)
        added = []
        known = {(s.kind, s.ref) for s in self.sources}
        for source in result.sources:
            if (source.kind, source.ref) in known or len(self.sources) >= 50:
                continue
            self.sources.append(source)
            known.add((source.kind, source.ref))
            added.append(source_dict(len(self.sources), source))
        return added

    def numbered(self, result: ToolResult) -> list[dict[str, Any]]:
        index = {(s.kind, s.ref): i + 1 for i, s in enumerate(self.sources)}
        return [source_dict(index[(s.kind, s.ref)], s) for s in result.sources if (s.kind, s.ref) in index]

    def finalize(self, text: str) -> tuple[str, list[dict[str, Any]], bool]:
        """(answer without invalid markers, cited sources, ``interpretation`` = nothing cited)."""
        cited: list[int] = []

        def keep(match: re.Match[str]) -> str:
            number = int(match.group(1))
            if 1 <= number <= len(self.sources):
                if number not in cited:
                    cited.append(number)
                return match.group(0)
            return ""

        clean = MARKER.sub(keep, text)
        sources = [source_dict(n, self.sources[n - 1]) for n in sorted(cited)]
        return clean, sources, not sources
