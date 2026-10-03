"""Community visibility (T003; R3, R4): the 021 datum classes Community owns and their owner-held
preference provider. Every surface asks the ``VisibilityFilter`` — after ``require()``, never instead —
so a permission alone never reveals Private data."""

from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.visibility import Level, register_datum_class
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import Redacted, VisibilityFilter
from portalab.modules.community.models import VisibilityPreference

OWNER = "module:community"
MEMBER_LISTING = "member_listing"
ACTIVITY = "community_activity"
PROJECTS = "projects"
VOTES = "votes"
CLASSES = (MEMBER_LISTING, ACTIVITY, PROJECTS, VOTES)
Surface = Literal["profile", "leaderboard", "listing", "history", "other"]

for _key, _level, _description in (
    (MEMBER_LISTING, "community", "Whether I appear in the members directory and search"),
    (ACTIVITY, "community", "My community activity (feed entries)"),
    (PROJECTS, "community", "The projects I propose or take part in"),
    (VOTES, "private", "Which projects I voted for"),
):
    register_datum_class(
        _key, owner=OWNER, default_level=_level, classification="activity", description=_description
    )


async def shown(
    visibility: VisibilityFilter,
    viewer: Principal,
    subject: UUID,
    datum: str,
    value: Any,
    surface: Surface = "profile",
) -> bool:
    try:
        result = await visibility.filter(viewer, subject, datum, None, value, surface=surface)  # type: ignore[call-arg]
    except TypeError:
        result = await visibility.filter(viewer, subject, datum, None, value)
    return not isinstance(result, Redacted)


class CommunityPreferences:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def get_preference(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level | None:
        if datum_class not in CLASSES:
            return None
        async with self.database.session() as session:
            row = await session.get(VisibilityPreference, (subject, datum_class))
        return cast(Level, row.level) if row else None

    async def set_preference(
        self, subject: UUID, datum_class: str, datum_ref: str | None, level: Level
    ) -> None:
        if datum_class not in CLASSES:
            raise ValidationFailed("Unknown datum class.", code="privacy.datum_not_found")
        now = utc_now(self.clock)
        statement = insert(VisibilityPreference).values(
            user_id=subject, datum_class=datum_class, level=level, updated_at=now
        )
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[VisibilityPreference.user_id, VisibilityPreference.datum_class],
                    set_={"level": level, "updated_at": now},
                )
            )
