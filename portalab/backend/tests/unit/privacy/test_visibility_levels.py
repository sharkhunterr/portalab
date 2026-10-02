"""021 T008 — level x viewer relationship x surface matrix; defaults never public."""

from uuid import uuid4

import pytest

from portalab.capabilities.visibility import DatumClassError, DatumClassRegistry
from portalab.core.authz_port import Principal
from portalab.modules.privacy.visibility.levels import relation_of, visible

pytestmark = pytest.mark.unit

OWNER = uuid4()

MATRIX = {
    # level: (self, member on profile, member on leaderboard, outsider)
    "public": (True, True, True, True),
    "community": (True, True, True, False),
    "leaderboard": (True, False, True, False),
    "private": (True, False, False, False),
}


@pytest.mark.parametrize("level", list(MATRIX))
def test_matrix(level: str) -> None:
    expected = MATRIX[level]
    assert visible(level, "self") is expected[0]  # type: ignore[arg-type]
    assert visible(level, "member", "profile") is expected[1]  # type: ignore[arg-type]
    assert visible(level, "member", "leaderboard") is expected[2]  # type: ignore[arg-type]
    assert visible(level, "outsider", "leaderboard") is expected[3]  # type: ignore[arg-type]


def test_relations() -> None:
    assert relation_of(Principal(user_id=OWNER), OWNER) == "self"
    assert relation_of(Principal(channel="ai", acting_for=OWNER), OWNER) == "self"
    assert relation_of(Principal(user_id=uuid4()), OWNER) == "member"
    assert relation_of(Principal(), OWNER) == "outsider"
    assert relation_of(Principal(channel="system"), OWNER) == "outsider"


def test_historized_classes_are_never_public_by_default() -> None:
    registry = DatumClassRegistry()
    for classification in ("history", "audit", "activity"):
        with pytest.raises(DatumClassError):
            registry.register(
                f"c_{classification}", owner="m", default_level="public", classification=classification
            )
    assert registry.register("bio", owner="m").default_level == "private"
