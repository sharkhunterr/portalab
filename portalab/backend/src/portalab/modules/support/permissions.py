"""Support permissions (T002). ``tickets.create``, ``tickets.manage``, ``incidents.manage`` and
``feedback.read`` belong to the core catalog (spec 003); the others are declared here."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:support"
INCIDENTS_READ = "incidents.read"
INCIDENTS_MANAGE = "incidents.manage"
SERVICES_READ = "services.read"


def declare_support_permissions(registry: PermissionRegistry = default_permissions) -> None:
    for key, description, roles, sensitive in (
        (INCIDENTS_READ, "See declared incidents and their public timeline", ("user",), False),
        ("tickets.comment", "Comment on own support tickets", ("user",), False),
        ("feedback.submit", "Send feedback, bug reports and feature requests", ("user",), False),
        ("feedback.convert", "Convert feedback into tickets or proposals", ("support",), True),
        ("feedback.convert.contribution", "Credit feedback as a contribution", ("moderator",), True),
        ("support.configure", "Configure ticket types, workflows and feedback forms", (), True),
    ):
        if registry.get(key) is None:
            registry.declare(key, description, sensitive=sensitive, default_roles=roles, owner=OWNER)


declare_support_permissions()
