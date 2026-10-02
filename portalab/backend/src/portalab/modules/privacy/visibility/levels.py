"""Visibility levels x viewer relationship x surface (FR-001..003). Pure functions.

Levels narrow the audience: public ⊃ community ⊃ leaderboard ⊃ private.

* ``self`` (the owner) always sees their own data;
* ``member`` (any signed-in account, including AI/automation acting for one) sees public and community data,
  and leaderboard-level data **only on leaderboard surfaces**;
* ``outsider`` (anonymous) sees public data only.

Permissions never enter here: privacy is a separate gate applied after ``require()`` (FR-002, FR-025).
"""

from typing import Literal
from uuid import UUID

from portalab.capabilities.visibility import Level
from portalab.core.authz_port import Principal

Relation = Literal["self", "member", "outsider"]
Surface = Literal["profile", "leaderboard", "listing", "history", "other"]


def relation_of(viewer: Principal, subject: UUID) -> Relation:
    acting = viewer.acting_for if viewer.channel in ("ai", "automation", "plugin") else viewer.user_id
    if acting is not None and acting == subject:
        return "self"
    if acting is not None:
        return "member"
    return "outsider"


def visible(level: Level, relation: Relation, surface: Surface = "profile") -> bool:
    if relation == "self":
        return True
    if level == "public":
        return True
    if relation == "outsider":
        return False
    if level == "community":
        return True
    if level == "leaderboard":
        return surface == "leaderboard"
    return False
