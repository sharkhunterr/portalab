"""Calendar permission ``calendar.read`` (every user by default); reminders are the caller's own."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:calendar"
CALENDAR_READ = "calendar.read"
SELF = "users.self.manage"


def declare_calendar_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(CALENDAR_READ) is None:
        registry.declare(CALENDAR_READ, "See the portal calendar", default_roles=("user",), owner=OWNER)


declare_calendar_permissions()
