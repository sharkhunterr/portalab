"""029: what a complete interface may read of the calendar (the exposure catalog)."""

from portalab.capabilities.exposure import read

A = "/api/v1"
LABELS = (
    read(f"{A}/calendar", "The calendar", "Le calendrier"),
    read(f"{A}/me/calendar/reminders", "Your reminders", "Vos rappels"),
)
