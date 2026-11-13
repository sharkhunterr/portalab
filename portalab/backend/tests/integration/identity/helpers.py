"""Helpers shared by identity integration and security tests."""

from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI

from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.common import SYSTEM
from portalab.modules.identity.services.credentials import set_password

PASSWORD = "correct horse battery"  # test fixture value, not a real credential


def module_of(app: FastAPI) -> IdentityModule:
    module = app.state.identity_module
    assert isinstance(module, IdentityModule)
    return module


async def create_user(
    module: IdentityModule,
    login: str,
    *,
    display_name: str | None = None,
    password: str | None = PASSWORD,
    state: AccountState = AccountState.ACTIVE,
) -> UUID:
    async with module.ctx.database.unit_of_work() as uow:
        user = await module.accounts.create_user(
            uow.session,
            login=login,
            display_name=display_name or login,
            email=None,
            state=state,
            actor=SYSTEM,
            reason="test",
        )
        if password is not None:
            await set_password(uow.session, module.hasher, user.id, password, module.ctx.now())
        return user.id


async def make_admin(module: IdentityModule, login: str = "admin") -> UUID:
    user_id = await create_user(module, login)
    async with module.ctx.database.session() as session:
        await module.ctx.admin_authority().grant_first_admin(session, user_id)
    return user_id


async def set_state(module: IdentityModule, user_id: UUID, state: AccountState) -> None:
    from sqlalchemy import update

    from portalab.modules.identity.models import User

    async with module.ctx.database.unit_of_work() as uow:
        await uow.session.execute(update(User).where(User.id == user_id).values(state=state.value))


async def login(client: httpx.AsyncClient, login_: str, password: str = PASSWORD) -> httpx.Response:
    response = await client.post("/api/v1/auth/login", json={"login": login_, "password": password})
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response


def comparable(problem: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in problem.items() if key != "correlation_id"}
