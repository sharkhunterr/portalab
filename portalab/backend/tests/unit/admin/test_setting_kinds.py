"""Issue 478: the System page edits a setting of several of a few (a list of choices) with one box each."""

from typing import Literal

from portalab.core.config_declaration import SettingCatalog
from portalab.modules.administration.api.routes import _kind


def test_a_list_of_choices_is_edited_as_several_boxes() -> None:
    catalog = SettingCatalog()
    several = catalog.declare(
        scope="global", key="t.countries", schema=list[Literal["DE", "US"]], default=[], description="x"
    )
    one = catalog.declare(
        scope="global", key="t.order", schema=Literal["a", "b"], default="a", description="x"
    )
    free = catalog.declare(scope="global", key="t.names", schema=list[str], default=[], description="x")
    assert _kind(several) == {"kind": "multi", "choices": ["DE", "US"]}
    assert _kind(one) == {"kind": "string", "choices": ["a", "b"]}
    assert _kind(free) == {"kind": "json"}
