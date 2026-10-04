"""``portalab demo seed`` — a fresh portal gets members, progression, achievements, quests, a Marketplace
catalog with owned items, community projects (one funding, one released), an active campaign, news, wiki,
support items and a broadcast, all through the module services; a second run adds nothing; generated
credentials land only in the 0600 users file."""

import secrets
from pathlib import Path

import pytest
from sqlalchemy import text

from portalab.app.demo_seed import MEMBERS, PRODUCTS, seed_demo
from portalab.app.wiring import wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.core.db import Database

pytestmark = pytest.mark.integration

COUNTS = {
    "users": "SELECT count(*) FROM identity.users",
    "transactions": "SELECT count(*) FROM gamification.transactions",
    "achievements": "SELECT count(*) FROM gamification.user_achievements",
    "products": "SELECT count(*) FROM marketplace.products WHERE state = 'available'",
    "ownerships": "SELECT count(*) FROM marketplace.ownerships",
    "projects": "SELECT count(*) FROM marketplace.projects",
    "fundings": "SELECT count(*) FROM marketplace.project_fundings",
    "campaigns": "SELECT count(*) FROM campaigns.campaigns",
    "articles": "SELECT count(*) FROM news.articles WHERE status = 'published'",
    "pages": "SELECT count(*) FROM wiki.pages",
    "tickets": "SELECT count(*) FROM support.tickets",
    "feedback": "SELECT count(*) FROM support.feedback_items",
}


async def counts(database: Database) -> dict[str, int]:
    async with database.session() as session:
        return {name: int(await session.scalar(text(sql)) or 0) for name, sql in COUNTS.items()}


async def test_seed_fills_every_domain_and_is_idempotent(database: Database, tmp_path: Path) -> None:
    platform = wire_platform(
        database, data_dir=tmp_path / "data", capabilities=new_registry(), secret_key=secrets.token_bytes(32)
    )
    await platform.authz.catalog.sync()
    await platform.refresh_config()
    admin = await platform.identity.bootstrap.create_first_admin(
        login="admin", password=secrets.token_urlsafe(16), display_name="Admin", email=None
    )
    users_file = tmp_path / "secrets" / "demo_users"

    first = await seed_demo(platform, users_file=users_file)
    skipped = {step: status for step, status in first.steps.items() if status.startswith("skipped")}
    assert first.ok and not skipped, first.steps
    assert first.steps["first run"] == "completed"
    after_first = await counts(database)
    assert after_first["users"] == 1 + len(MEMBERS)
    assert after_first["products"] == len(PRODUCTS) and after_first["ownerships"] >= 3
    assert after_first["projects"] == 2 and after_first["fundings"] >= 5
    assert after_first["achievements"] >= 10 and after_first["campaigns"] == 1
    assert after_first["articles"] == 3 and after_first["pages"] >= 3
    assert after_first["tickets"] == 2 and after_first["feedback"] == 2

    progression = await platform.gamification.progression.progress(admin)
    assert progression.level >= 4 and progression.coins > 0

    lines = users_file.read_text(encoding="utf-8").splitlines()
    assert [line.split("\t")[0] for line in lines] == [login for login, _ in MEMBERS]
    assert users_file.stat().st_mode & 0o777 == 0o600

    second = await seed_demo(platform, users_file=users_file)
    assert second.ok and second.created_users == []
    assert await counts(database) == after_first  # nothing added
    assert len(users_file.read_text(encoding="utf-8").splitlines()) == len(MEMBERS)
