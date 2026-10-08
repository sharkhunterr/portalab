"""``authentik`` connector: Authentik, the homelab's single sign-on — accounts and the groups that open each
service (027).

* ``identity.provisioning``: find a member's account (by email, else username), create it, add it to or
  remove it from a group, and get a one-time recovery link for the member to set their password — what an
  approved service access does.
* ``service.accounts``: Authentik's users, to match with portal members.
* ``service.health_probe``: an authenticated ``/api/v3/core/users/me/`` round trip.

Authentication uses an API token (*Directory → Tokens and App passwords*, intent « API ») of an account
allowed to manage users and groups.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.identity_provider import PROVISIONING
from portalab.capabilities.media import ACCOUNTS, ServiceAccount
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding

API = "/api/v3"


class AuthentikConnector(HttpConnector):
    key = "authentik"
    name = "Authentik"
    description = "Your single sign-on: the accounts and the groups that open each service."
    icon = "shield"
    category = "identity"
    config_schema: type[BaseModel] = BaseConfig
    secret_fields: frozenset[str] = frozenset({"api_token"})
    provides: Sequence[CapabilityBinding] = (
        binding(HEALTH_PROBE),
        binding(ACCOUNTS),
        binding(PROVISIONING),
    )
    status_path = f"{API}/core/users/me/"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {"Authorization": f"Bearer {service.secrets.get('api_token', '')}"}

    def describe(self, status: Any) -> str:
        user = status.get("user") if isinstance(status, Mapping) else None
        if not isinstance(user, Mapping) or "username" not in user:
            raise InvalidPayload("not an Authentik user")
        return f"Authentik (as {user['username']})"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        if capability == ACCOUNTS:
            return _Accounts(self, service)
        if capability == PROVISIONING:
            return Provisioning(self, service)
        return None


def _results(page: Any) -> list[Mapping[str, Any]]:
    if not isinstance(page, Mapping) or not isinstance(page.get("results"), list):
        raise InvalidPayload("unexpected Authentik list")
    return [r for r in page["results"] if isinstance(r, Mapping)]


class _Accounts:
    def __init__(self, connector: AuthentikConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def list_accounts(self) -> Sequence[ServiceAccount]:
        out: list[ServiceAccount] = []
        page = 1
        while page and page <= 50:
            answer = await self.connector.get_json(
                self.service, f"{API}/core/users/", page=page, page_size=200, type="internal"
            )
            out.extend(
                ServiceAccount(external_id=str(u["pk"]), username=u.get("username"), email=u.get("email"))
                for u in _results(answer)
                if u.get("pk") is not None
            )
            pagination = answer.get("pagination") if isinstance(answer, Mapping) else None
            page = int(pagination.get("next") or 0) if isinstance(pagination, Mapping) else 0
        return out


class Provisioning:
    """Accounts and groups in Authentik, for a service's access."""

    def __init__(self, connector: AuthentikConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def _get(self, path: str, **params: Any) -> Any:
        return await self.connector.get_json(self.service, f"{API}{path}", **params)

    async def _post(self, path: str, body: Any) -> Any:
        return await self.connector.request(self.service, "POST", f"{API}{path}", json_body=body)

    async def find_user(self, email: str | None, username: str | None) -> str | None:
        for field, value in (("email", email), ("username", username)):
            if value:
                found = _results(await self._get("/core/users/", **{field: value}))
                if found:
                    return str(found[0]["pk"])
        return None

    async def create_user(self, username: str, name: str, email: str | None) -> str:
        body = {"username": username, "name": name or username, "is_active": True, "path": "users"}
        if email:
            body["email"] = email
        created = await self._post("/core/users/", body)
        if not isinstance(created, Mapping) or created.get("pk") is None:
            raise InvalidPayload("Authentik did not create the account")
        return str(created["pk"])

    async def _group(self, name: str) -> str:
        found = _results(await self._get("/core/groups/", name=name))
        if not found:
            raise InvalidPayload(f"no Authentik group named « {name} »")
        return str(found[0]["pk"])

    async def add_to_group(self, user: str, group: str) -> None:
        await self._post(f"/core/groups/{await self._group(group)}/add_user/", {"pk": int(user)})

    async def remove_from_group(self, user: str, group: str) -> None:
        await self._post(f"/core/groups/{await self._group(group)}/remove_user/", {"pk": int(user)})

    async def recovery_link(self, user: str) -> str | None:
        try:
            answer = await self._post(f"/core/users/{int(user)}/recovery/", {})
        except Exception:
            return None  # no recovery flow set on the brand: the member uses « forgot password »
        link = answer.get("link") if isinstance(answer, Mapping) else None
        return str(link) if isinstance(link, str) and link.startswith("https://") else None
