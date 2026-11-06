"""Requests settings (issue 363, #378), declared to Administration: one record, ``requests.config`` — the
kinds of titles the team takes requests for (the films and series go to the request service). Quotas,
units bought in the shop and rewards are those of every request."""

from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:requests"
KEY = "requests.config"
Kind = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$", max_length=40)]


class RequestsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kinds: list[Kind] = Field(default_factory=lambda: ["book", "audiobook", "game"], max_length=40)


def normalized(value: dict[str, Any]) -> dict[str, Any]:
    config = RequestsConfig.model_validate(value)
    # a film or a series is the request service's: never the team's
    config.kinds = [k for k in dict.fromkeys(config.kinds) if k not in ("movie", "series", "season", "tv")]
    return config.model_dump(mode="json")


def config_of(value: Any) -> RequestsConfig:
    try:
        return RequestsConfig.model_validate(value or {})
    except ValueError:
        return RequestsConfig()


Schema = Annotated[dict[str, Any], AfterValidator(normalized)]


def declare_requests_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    if KEY not in {d.key for d in catalog.all()}:
        declare(
            scope="global",
            key=KEY,
            schema=Schema,
            default=normalized({}),
            owner=OWNER,
            description=(
                "The kinds of titles members ask the team for (books, audiobooks, games…): their requests "
                "are the portal's, with the films' and series' — the same queue, quotas and figures."
            ),
        )


declare_requests_settings()
