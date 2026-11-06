"""Requests permissions (issue 363): ``requests.ask`` — ask for a title, say « me too » (default user grant);
``requests.manage`` — the administrators' queue: accept, refuse, mark a request done, set the module up."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:requests"
ASK = "requests.ask"
MANAGE = "requests.manage"


def declare_requests_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(ASK) is None:
        registry.declare(
            ASK, "Ask for a title the library lacks, say « me too »", default_roles=("user",), owner=OWNER
        )
    if registry.get(MANAGE) is None:
        registry.declare(MANAGE, "Handle the members' requests", sensitive=True, owner=OWNER)


declare_requests_permissions()
