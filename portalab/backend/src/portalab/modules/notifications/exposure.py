"""029: what an extension may read or do with the member's notifications (the exposure catalog)."""

from portalab.capabilities.exposure import action, read

A = "/api/v1"
LABELS = (
    read(
        f"{A}/me/notifications", "Your notifications", "Vos notifications", topics=("notifications.created",)
    ),
    read(f"{A}/me/notifications/unread-count", "How many are unread", "Le nombre de non lues"),
    read(f"{A}/announcements/banners", "Announcements", "Les annonces"),
    action(
        "POST",
        f"{A}/me/notifications/{{notification_id}}/read",
        "Mark a notification read",
        "Marquer une notification comme lue",
    ),
    action("POST", f"{A}/me/notifications/read-all", "Mark every notification read", "Tout marquer comme lu"),
    action(
        "POST",
        f"{A}/me/notifications/{{notification_id}}/archive",
        "Archive a notification",
        "Archiver une notification",
    ),
)
