"""The AI acts **for** a user and never with more rights (CD-003): every tool runs as
``Principal(channel="ai", acting_for=<user>)``, which the authorization engine checks against the user's
grants *and* ``ai.use``."""

from uuid import UUID

from portalab.core.authz_port import Principal


def subject_of(principal: Principal) -> UUID:
    subject = principal.acting_for if principal.channel != "user" else principal.user_id
    if subject is None:
        raise ValueError("the assistant acts for an identified user only")
    return subject


def ai_principal(principal: Principal) -> Principal:
    return Principal(channel="ai", acting_for=subject_of(principal), session_id=principal.session_id)
