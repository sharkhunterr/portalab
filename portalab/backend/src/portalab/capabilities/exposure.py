"""The exposure catalog (spec 029): what Portalab opens to an extension, operation by operation.

Every operation of the API carries a label — ``read``, ``action`` (a simple action: mark read, favourite),
``committing`` (it engages the member: buying, opening a booster, requesting, deleting, publishing) or
``forbidden``. Each module declares the labels of its own routes (``modules/<m>/exposure.py``, data only);
the **forbidden prefixes win** over any declaration (administration, authentication, account, security,
privacy, settings, the packs' own plumbing), and **a route nobody labelled is forbidden**. Spec 030 scopes
what an extension's code may call with it; ``GET /api/v1/exposure`` lists it in plain words.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

PREFIX = "/api/v1"


class Exposure(StrEnum):
    READ = "read"
    ACTION = "action"
    COMMITTING = "committing"
    FORBIDDEN = "forbidden"


# what an interface never reaches, whatever a module says
FORBIDDEN_PREFIXES: tuple[str, ...] = tuple(
    f"{PREFIX}{p}"
    for p in (
        "/admin",
        "/auth",
        "/users",
        "/roles",
        "/groups",
        "/permissions",
        "/grants",
        "/audit",
        "/maintenance",
        "/privacy",
        "/plugins",
        "/connectors",
        "/infrastructure",
        "/services",
        "/incidents",
        "/diagnosis",
        "/health",
        "/ai",
        "/exposure",
        "/visuals",
        "/i18n",
        "/ui",
        "/me/security",
        "/me/sessions",
        "/me/seal",
        "/me/account",
        "/me/deletion",
        "/me/export",
        "/me/privacy",
        "/me/preferences",
        "/me/profile",
        "/me/avatar",
        "/me/terms",
        "/me/permissions",
        "/me/newsletters",
        "/me/notification-preferences",
        "/me/statistics/preferences",
        "/me/onboarding",
        "/me/media/links",
        "/me/marketplace/owned",
        "/me/search-history",
        "/me/feedback",
        "/me/tickets",
        # the media streams and reading tickets: Portalab's own player and reader only
        "/media/player",
        "/media/read",
        "/media/listen",
    )
)
_STREAMS = frozenset({"player", "read", "listen"})


def operation_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def forbidden_by_prefix(path: str) -> bool:
    """Administration, authentication, account, security, privacy, settings, streams, the packs' plumbing."""
    return _forbidden_by_prefix(path)


def _forbidden_by_prefix(path: str) -> bool:
    if any(path == p or path.startswith(p + "/") for p in FORBIDDEN_PREFIXES):
        return True
    # a title's own player, reader and listening routes (``/media/{object_id}/player/start``…)
    return path.startswith(f"{PREFIX}/media/") and bool(_STREAMS & set(path.split("/")))


@dataclass(frozen=True, slots=True)
class OperationLabel:
    method: str
    path: str
    exposure: Exposure
    words: Mapping[str, str]  # {en, fr}: what it reads or does, in plain words
    confirm: Mapping[str, str] | None = None  # committing: what the trust layer states
    topics: tuple[str, ...] = ()  # live topics a read covers (forwarded to the interface)

    @property
    def key(self) -> str:
        return operation_key(self.method, self.path)

    def out(self) -> dict[str, Any]:
        return {
            "operation": self.key,
            "exposure": self.exposure.value,
            "words": dict(self.words),
            **({"confirm": dict(self.confirm)} if self.confirm else {}),
            **({"topics": list(self.topics)} if self.topics else {}),
        }


class ExposureError(ValueError):
    """A label contradicting the catalog's rules (a module's mistake, caught at start and by the tests)."""


def read(path: str, en: str, fr: str, *, topics: Iterable[str] = ()) -> OperationLabel:
    return OperationLabel("GET", path, Exposure.READ, {"en": en, "fr": fr}, topics=tuple(topics))


def action(method: str, path: str, en: str, fr: str) -> OperationLabel:
    return OperationLabel(method, path, Exposure.ACTION, {"en": en, "fr": fr})


def committing(
    method: str, path: str, en: str, fr: str, *, confirm_en: str, confirm_fr: str
) -> OperationLabel:
    return OperationLabel(
        method, path, Exposure.COMMITTING, {"en": en, "fr": fr}, {"en": confirm_en, "fr": confirm_fr}
    )


class ExposureRegistry:
    def __init__(self) -> None:
        self._labels: dict[str, OperationLabel] = {}

    def declare(self, *labels: OperationLabel) -> None:
        for label in labels:
            method = label.method.upper()
            if not label.path.startswith(f"{PREFIX}/"):
                raise ExposureError(f"{label.key}: not an API path")
            if label.exposure is Exposure.READ and method != "GET":
                raise ExposureError(f"{label.key}: only a GET may be a read")
            if method == "GET" and label.exposure in (Exposure.ACTION, Exposure.COMMITTING):
                raise ExposureError(f"{label.key}: a GET may only be a read")
            if label.exposure is Exposure.COMMITTING and not (label.confirm and label.confirm.get("en")):
                raise ExposureError(f"{label.key}: a committing operation needs its confirmation words")
            self._labels[label.key] = label

    def resolve(self, method: str, path: str) -> OperationLabel:
        """The label of an operation (``path``: the route's template) — forbidden by prefix or by silence."""
        key = operation_key(method, path)
        label = self._labels.get(key)
        if _forbidden_by_prefix(path) or label is None:
            return OperationLabel(method.upper(), path, Exposure.FORBIDDEN, label.words if label else {})
        return label

    def exposable(self) -> list[OperationLabel]:
        return [
            label
            for label in sorted(self._labels.values(), key=lambda lab: lab.key)
            if self.resolve(label.method, label.path).exposure is not Exposure.FORBIDDEN
        ]

    def declared(self) -> Mapping[str, OperationLabel]:
        return dict(self._labels)


default_exposure = ExposureRegistry()
