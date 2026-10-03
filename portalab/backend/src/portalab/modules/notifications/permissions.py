"""Notification permissions (T002): managing the transport and categories, broadcasting to everyone and
targeting an audience are separate, audited capabilities (none granted by default)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:notifications"
NOTIFICATIONS_MANAGE = "notifications.manage"
NOTIFICATIONS_BROADCAST = "notifications.broadcast"
SEND_TO_AUDIENCE = "notifications.send_to_audience"
SELF = "users.self.manage"


def declare_notification_permissions(registry: PermissionRegistry = default_permissions) -> None:
    for key, description in (
        (NOTIFICATIONS_MANAGE, "Configure notification categories and e-mail delivery"),
        (NOTIFICATIONS_BROADCAST, "Send a communication to every user"),
        (SEND_TO_AUDIENCE, "Send a communication to an audience (users, permission holders, a role)"),
    ):
        if registry.get(key) is None:
            registry.declare(key, description, sensitive=True, owner=OWNER)


declare_notification_permissions()
