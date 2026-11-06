"""Requests permissions (issue 363): ``requests.manage`` — set up the kinds of titles the team takes. Asking
for a title and deciding on a request are the media's (``media.request``, ``media.manage``)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:requests"
MANAGE = "requests.manage"


def declare_requests_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(MANAGE) is None:
        registry.declare(MANAGE, "Set up the kinds of titles asked of the team", sensitive=True, owner=OWNER)


declare_requests_permissions()
