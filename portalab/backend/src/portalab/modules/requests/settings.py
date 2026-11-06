"""Requests settings (issue 363), declared to Administration: one record, ``requests.config`` — the kinds of
titles members may ask for (the films and series go to the request service), how many requests of a kind a
member may make over so many days, and what a request costs in Coins (none by default). The rewards are the
reward rules' (``requests.created``, ``requests.supported``, ``requests.fulfilled``)."""

from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:requests"
KEY = "requests.config"
Kind = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$", max_length=40)]


class Quota(BaseModel):
    """At most ``limit`` requests of a kind over ``days`` days (0: no limit)."""

    model_config = ConfigDict(extra="ignore")
    limit: int = Field(default=0, ge=0, le=1000)
    days: int = Field(default=30, ge=1, le=365)


class RequestsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kinds: list[Kind] = Field(default_factory=lambda: ["book", "audiobook", "game"], max_length=40)
    quotas: dict[Kind, Quota] = Field(default_factory=dict)
    price: int = Field(default=0, ge=0, le=1_000_000)  # Coins a request costs; given back when refused

    def quota(self, kind: str) -> Quota:
        return self.quotas.get(kind) or Quota()


def normalized(value: dict[str, Any]) -> dict[str, Any]:
    config = RequestsConfig.model_validate(value)
    config.kinds = list(dict.fromkeys(config.kinds))
    config.quotas = {k: q for k, q in config.quotas.items() if k in config.kinds}
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
                "The members' requests to the administrators: the kinds of titles they may ask for, how many "
                "requests of a kind a member may make over so many days, what a request costs in Coins "
                "(given back when refused). Rewards: the reward rules of requests.created, "
                "requests.supported and requests.fulfilled."
            ),
        )


declare_requests_settings()
