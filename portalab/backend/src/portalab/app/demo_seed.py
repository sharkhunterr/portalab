"""Demo data (``portalab demo seed``): a lived-in portal for manual tests and demos.

Everything goes through the modules' own services — accounts, rewards, catalog, purchases, projects,
fundings, campaigns, news, wiki, support, notifications — so business rules, audit, events and the
economy ledger stay consistent (no raw writes; reads only to check what already exists). Each domain is
an independent step: a step that cannot run (module disabled, definition refused…) is reported as
skipped and the others continue. Every step is idempotent — natural keys (logins, product/rule/quest
keys, titles, slugs) and idempotency keys make a second run add nothing.

Demo members get random passwords, appended to a file readable by its owner only; they are never
printed or logged.
"""

import os
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from portalab.app.wiring import Platform
from portalab.capabilities.notifications import AllAuthenticated, CommunicationRequest
from portalab.capabilities.support import TicketRequest
from portalab.core.authz_port import Principal
from portalab.core.logging import get_logger
from portalab.core.time import utc_now
from portalab.modules.gamification.achievements.definition import parse_achievement
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.services.common import SYSTEM
from portalab.modules.identity.services.credentials import set_password
from portalab.modules.news.articles import ArticleInput
from portalab.modules.wiki.pages import PageInput

log = get_logger("portalab.demo")

MEMBERS = (("alice", "Alice Martin"), ("bruno", "Bruno Lefèvre"), ("chloe", "Chloé Dubois"))

# Target progression (default curve: level n from 100*(n-1)^1.5 XP) — a portal that looks played.
PROGRESSION: dict[str, dict[str, int]] = {
    "admin": {"xp": 900, "coins": 450, "contribution": 3},  # level 5
    "alice": {"xp": 1300, "coins": 380, "contribution": 5},  # level 6
    "bruno": {"xp": 600, "coins": 240, "contribution": 2},  # level 4
    "chloe": {"xp": 260, "coins": 120, "contribution": 1},  # level 2
}

ACHIEVEMENTS: dict[str, dict[str, Any]] = {
    "first_steps": {
        "category": "service_usage",
        "label": "First steps",
        "description": "Sign in to the portal for the first time.",
        "icon": "sparkles",
        "criteria": [{"kind": "event_count", "event_type": "user.signed_in", "count": 1}],
        "rewards": [{"value": "coins", "amount": 10}],
    },
    "regular": {
        "category": "service_usage",
        "label": "Regular",
        "description": "Sign in on ten different occasions.",
        "icon": "calendar",
        "criteria": [{"kind": "event_count", "event_type": "user.signed_in", "count": 10}],
        "rewards": [{"value": "xp", "amount": 50}],
    },
    "saver": {
        "category": "purchase",
        "label": "Saver",
        "description": "Hold at least 200 Coins.",
        "icon": "coins",
        "criteria": [{"kind": "value_at_least", "value": "coins", "amount": 200}],
    },
    "rising_star": {
        "category": "progression",
        "label": "Rising star",
        "description": "Reach level 3.",
        "icon": "star",
        "criteria": [{"kind": "level_at_least", "level": 3}],
        "rewards": [{"value": "coins", "amount": 25}],
    },
    "veteran": {
        "category": "progression",
        "label": "Veteran",
        "description": "Reach level 5.",
        "icon": "trophy",
        "criteria": [{"kind": "level_at_least", "level": 5}],
        "rewards": [{"value": "coins", "amount": 50}],
    },
    "night_owl": {
        "category": "other",
        "label": "Night owl",
        "description": "A secret achievement.",
        "icon": "moon",
        "hidden": True,
        "criteria": [{"kind": "value_at_least", "value": "coins", "amount": 5000}],
    },
}

ACHIEVEMENTS |= {
    "first_purchase": {
        "category": "purchase",
        "label": "First purchase",
        "description": "Buy something in the shop.",
        "icon": "shop",
        "criteria": [{"kind": "event_count", "event_type": "marketplace.purchase", "count": 1}],
        "rewards": [{"value": "xp", "amount": 20}],
    },
    "collector": {
        "category": "purchase",
        "label": "Collector",
        "description": "Own three items from the shop.",
        "icon": "star",
        "criteria": [{"kind": "event_count", "event_type": "marketplace.purchase", "count": 3}],
        "rewards": [{"value": "coins", "amount": 40}],
    },
    "pillar": {
        "category": "community",
        "label": "Pillar of the community",
        "description": "Reach 25 Contribution points.",
        "icon": "heart",
        "criteria": [{"kind": "value_at_least", "value": "contribution", "amount": 25}],
    },
}

# 027 US8: shop collections (marketplace categories) and presentation of each product
COLLECTIONS: tuple[tuple[str, str, str, int], ...] = (
    ("halloween", "Halloween", "moon", 10),
    ("new_wave", "New Wave", "zap", 20),
    ("essentials", "Essentials", "star", 30),
)
PRESENTATION: dict[
    str, tuple[str, str, bool, str, str | None]
] = {  # rarity, effect, featured, collection, icon
    "badge_pioneer": ("common", "none", False, "essentials", "compass"),
    "badge_night_owl": ("rare", "shine", False, "halloween", "moon"),
    "title_legend": ("legendary", "neon", True, "essentials", "trophy"),
    "title_cinephile": ("rare", "shine", False, "essentials", "film"),
    "effect_confetti": ("epic", "spin", False, "new_wave", "sparkles"),
    "effect_aurora": ("epic", "glitch", True, "new_wave", "sparkles"),
    "theme_orbit": ("legendary", "neon", True, "new_wave", "compass"),
    "theme_studio": ("rare", "shine", False, "essentials", "palette"),
    "effect_pumpkin": ("epic", "blink", False, "halloween", "sparkles"),
    "badge_ghost": ("legendary", "glitch", True, "halloween", "moon"),
    "quota_requests": ("common", "none", False, "essentials", "inbox"),
}

QUESTS: dict[str, dict[str, Any]] = {
    "daily_visit": {
        "kind": "daily",
        "label": "Daily visit",
        "description": "Drop by the portal today.",
        "icon": "home",
        "period": "day",
        "steps": [{"kind": "event_count", "event_type": "user.signed_in", "count": 1}],
        "rewards": [{"value": "coins", "amount": 5}],
    },
    "weekly_regular": {
        "kind": "daily",
        "label": "Weekly regular",
        "description": "Sign in on three occasions this week.",
        "icon": "calendar",
        "period": "week",
        "steps": [{"kind": "event_count", "event_type": "user.signed_in", "count": 3}],
        "rewards": [{"value": "xp", "amount": 30}],
    },
    "explorer": {
        "kind": "quest",
        "label": "Explorer",
        "description": "Come back five times to discover everything.",
        "icon": "compass",
        "steps": [{"kind": "event_count", "event_type": "user.signed_in", "count": 5}],
        "rewards": [{"value": "xp", "amount": 80}, {"value": "coins", "amount": 20}],
    },
}

RULES: dict[str, dict[str, Any]] = {
    "sign_in_bonus": {"event_type": "user.signed_in", "grants": [{"value": "xp", "amount": 5}]},
}


def _product(key: str, kind: str, price: int, en: str, fr: str, desc: str, payload: dict[str, Any]) -> Any:
    return {
        "key": key,
        "type": kind,
        "version": {
            "price_coins": price,
            "names": {"en": en, "fr": fr},
            "descriptions": {"en": desc},
            "payload": payload,
        },
    }


PRODUCTS: tuple[dict[str, Any], ...] = (
    _product(
        "badge_pioneer", "badge", 50, "Pioneer badge", "Badge Pionnier",
        "For the first members of the portal.", {"label": "Pioneer", "icon": "compass"},
    ),
    _product(
        "badge_night_owl", "badge", 120, "Night owl badge", "Badge Oiseau de nuit",
        "For those who watch until dawn.", {"label": "Night owl", "icon": "moon"},
    ),
    _product(
        "title_legend", "title", 300, "Title: Legend", "Titre : Légende",
        "Show a legendary title on your profile.", {"label": "Legend"},
    ),
    _product(
        "title_cinephile", "title", 150, "Title: Cinephile", "Titre : Cinéphile",
        "For lovers of the big screen.", {"label": "Cinephile"},
    ),
    _product(
        "effect_confetti", "effect", 80, "Confetti effect", "Effet confettis",
        "Celebrate your level-ups with confetti.", {"effect": "confetti"},
    ),
    _product(
        "effect_aurora", "effect", 200, "Aurora effect", "Effet aurore",
        "A soft aurora behind your profile.", {"effect": "aurora"},
    ),
    _product(
        "theme_orbit", "theme", 400, "Orbit theme", "Thème Orbite",
        "Navigation in an orbiting bubble, header at the bottom, playful motion.", {"theme": "orbit"},
    ),
    _product(
        "theme_studio", "theme", 250, "Studio theme", "Thème Studio",
        "A calm studio: top bar, flat cards, narrow reading width.", {"theme": "studio"},
    ),
    _product(
        "effect_pumpkin", "effect", 180, "Pumpkin glow", "Lueur citrouille",
        "A flickering pumpkin glow for the spooky season.", {"effect": "pumpkin"},
    ),
    _product(
        "badge_ghost", "badge", 500, "Ghost badge", "Badge Fantôme",
        "Only the bravest haunt the portal at night.", {"label": "Ghost", "icon": "moon"},
    ),
    _product(
        "quota_requests", "quota", 60, "+5 media requests", "+5 demandes de médias",
        "Five extra media requests this month.", {"kind": "media_requests", "units": 5},
    ),
)  # fmt: skip
OWNED_BY_ADMIN = ("badge_pioneer", "effect_confetti")
OWNED_BY_ALICE = ("badge_night_owl",)

FUNDING_RULES = {"consume_at": "released", "min_funding": 5, "max_funding_per_user": 300}
PROJECTS: tuple[tuple[str, str, dict[str, int], str], ...] = (
    ("demo-offline-mode", "Offline mode", {"alice": 120, "bruno": 60, "admin": 40}, "released"),
    ("demo-shared-playlists", "Shared playlists", {"alice": 80, "chloe": 30}, "open"),
)

ARTICLES: tuple[tuple[str, str, str], ...] = (
    (
        "Welcome to the new Portalab",
        "A brand new look, a personal header and a menu organised by sections.",
        "## A fresh start\n\nThe portal has a **new design**: your level and Coins are always visible, the "
        "menu is grouped by sections and everything works on your phone.\n\nTell us what you think in "
        "*Support → Feedback*.",
    ),
    (
        "Autumn festival: double rewards",
        "The autumn festival is on — earn more XP while it lasts.",
        "## Autumn festival\n\nUntil the end of the event, rewards are boosted. Complete the daily "
        "objectives to climb the leaderboard!",
    ),
    (
        "Community projects are open",
        "Fund the features you want with your Coins.",
        "## Your Coins, your portal\n\nCommunity projects let you **reserve Coins** for the features you "
        "want. Funding never guarantees delivery; reserved Coins are returned if a project is abandoned.",
    ),
)

WIKI: tuple[tuple[str, str, str], ...] = (
    (
        "getting-started",
        "Getting started",
        "# Getting started\n\n1. Open the **menu** to browse the sections.\n2. Your **avatar** gives access "
        "to your profile, appearance and language.\n3. Earn XP and Coins by using the portal; spend Coins "
        "in the **Marketplace** or fund **community projects**.",
    ),
    (
        "levels-and-coins",
        "Levels, XP and Coins",
        "# Levels, XP and Coins\n\n- **XP** measures your progression and sets your level.\n- **Coins** are "
        "a virtual currency (never real money) for the Marketplace and projects.\n- **Contribution** "
        "recognises what you bring to the community.",
    ),
    (
        "faq",
        "Frequently asked questions",
        "# FAQ\n\n**How do I change the theme?** Avatar → Appearance.\n\n**Where are my requests?** "
        "Media → Requests.\n\n**Who can see my progression?** Your privacy settings decide.",
    ),
)

TICKETS: tuple[tuple[str, str, str, str, dict[str, str]], ...] = (
    ("alice", "question", "How do I link my media account?", "I cannot find where to link my account.", {}),
    (
        "bruno",
        "bug",
        "Poster missing on a film page",
        "One film shows no poster on its detail page.",
        {"steps": "Open Media, then a film detail page.", "expected": "The poster", "impact": "low"},
    ),
)
FEEDBACK: tuple[tuple[str, str, dict[str, str]], ...] = (
    ("chloe", "feature_request", {"idea": "A dark theme with more contrast", "why": "Easier at night"}),
    ("bruno", "general", {"message": "The new menu is much clearer, thanks!"}),
)


@dataclass
class SeedReport:
    steps: dict[str, str] = field(default_factory=dict)
    created_users: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(not status.startswith("failed") for status in self.steps.values())


class DemoSeeder:
    def __init__(self, platform: Platform, *, users_file: Path | None = None) -> None:
        self.platform = platform
        self.database = platform.identity.ctx.database
        self.users_file = users_file
        self.people: dict[str, UUID] = {}
        self.report = SeedReport()

    # ------------------------------------------------------------------------------------------- helpers
    async def _scalar(self, sql: str, **params: Any) -> Any:
        async with self.database.session() as session:
            return await session.scalar(text(sql), params)

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])

    @property
    def admin(self) -> Principal:
        return self.p("admin")

    async def _step(self, name: str, work: Callable[[], Awaitable[str]]) -> None:
        try:
            self.report.steps[name] = await work()
        except Exception as exc:  # one domain never blocks the others
            log.warning("demo seed step skipped", extra={"step": name, "error": type(exc).__name__})
            self.report.steps[name] = f"skipped ({type(exc).__name__}: {str(exc)[:160]})"

    # -------------------------------------------------------------------------------------------- steps
    async def run(self) -> SeedReport:
        admin = await self._scalar("SELECT current_admin_user_id FROM authz.admin_singleton LIMIT 1")
        if admin is None:
            self.report.steps["admin"] = "failed (no Admin yet: run `portalab admin bootstrap` first)"
            return self.report
        self.people["admin"] = admin
        await self._step("members", self.members)
        await self._step("gamification definitions", self.gamification_definitions)
        await self._step("progression", self.progression)
        await self._step("achievements unlocked", self.unlock_achievements)
        await self._step("marketplace catalog", self.catalog)
        await self._step("marketplace purchases", self.purchases)
        await self._step("community projects", self.projects)
        await self._step("campaign", self.campaign)
        await self._step("news", self.news)
        await self._step("wiki", self.wiki)
        await self._step("support", self.support)
        await self._step("notifications", self.notifications)
        await self._step("leaderboards", self.leaderboards)
        return self.report

    async def members(self) -> str:
        identity = self.platform.identity
        created: list[tuple[str, str]] = []
        for login, name in MEMBERS:
            existing = await self._scalar("SELECT id FROM identity.users WHERE login = :l", l=login)
            if existing is not None:
                self.people[login] = existing
                continue
            password = secrets.token_urlsafe(18)
            async with self.database.unit_of_work() as uow:
                user = await identity.accounts.create_user(
                    uow.session,
                    login=login,
                    display_name=name,
                    email=None,
                    state=AccountState.ACTIVE,
                    actor=SYSTEM,
                    reason="demo data",
                )
                await set_password(uow.session, identity.hasher, user.id, password, identity.ctx.now())
                self.people[login] = user.id
            created.append((login, password))
        if created:
            self._write_credentials(created)
            self.report.created_users = [login for login, _ in created]
        return f"{len(created)} created, {len(MEMBERS) - len(created)} existing"

    def _write_credentials(self, created: list[tuple[str, str]]) -> None:
        if self.users_file is None:
            log.warning("demo members created without a credentials file: reset their passwords to use them")
            return
        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.users_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            for login, password in created:
                handle.write(f"{login}\t{password}\n")
        self.users_file.chmod(0o600)

    async def gamification_definitions(self) -> str:
        gamification = self.platform.gamification
        made = 0
        for key, raw in ACHIEVEMENTS.items():
            stored = await self._scalar(
                "SELECT definition FROM gamification.achievements WHERE key = :k "
                "ORDER BY version DESC LIMIT 1",
                k=key,
            )
            if stored is not None and stored == parse_achievement(raw).model_dump():
                continue  # unchanged: idempotent
            await gamification.achievements.save(self.admin, key, raw)  # new definition or new version
            made += 1
        for key, raw in QUESTS.items():
            if await self._scalar("SELECT 1 FROM gamification.quests WHERE key = :k LIMIT 1", k=key):
                continue
            await gamification.quests.save(self.admin, key, raw)
            made += 1
        for key, raw in RULES.items():
            if await self._scalar("SELECT 1 FROM gamification.reward_rules WHERE key = :k LIMIT 1", k=key):
                continue
            rule = await gamification.rules.save(self.admin, key, raw)
            await gamification.rules.publish(self.admin, key, rule.version)
            made += 1
        return f"{made} definitions created"

    async def progression(self) -> str:
        rewards = self.platform.gamification.rewards
        granted = 0
        for name, values in PROGRESSION.items():
            if name not in self.people:
                continue
            for value, amount in values.items():
                if value == "contribution":
                    for index in range(amount):
                        source = f"demo:{name}:{index}"
                        if await self._scalar(
                            "SELECT 1 FROM gamification.transactions WHERE idempotency_key = :k",
                            k=f"contribution:{source}",
                        ):
                            continue
                        result = await rewards.grant_contribution(
                            self.people[name], "demo", source, self.admin
                        )
                        granted += result != "withheld"
                    continue
                done = await rewards.grant_manual(
                    self.admin,
                    self.people[name],
                    value,  # type: ignore[arg-type]
                    amount,
                    reason="Demo data",
                    idempotency_key=f"demo:{name}:{value}",
                )
                granted += done is not None and not done.duplicate
        return f"{granted} new grants"

    async def unlock_achievements(self) -> str:
        rewards = self.platform.gamification.rewards
        unlocked = 0
        for name, keys in (
            ("admin", ("first_steps", "saver", "rising_star", "veteran")),
            ("alice", ("first_steps", "regular", "saver", "rising_star", "veteran")),
            ("bruno", ("first_steps", "saver", "rising_star")),
            ("chloe", ("first_steps",)),
        ):
            if name not in self.people:
                continue
            for key in keys:
                unlocked += bool(await rewards.unlock(self.admin, self.people[name], key))
        return f"{unlocked} newly unlocked"

    async def catalog(self) -> str:
        from portalab.modules.marketplace.products.definition import PresentationIn

        catalog = self.platform.marketplace.catalog
        for key, label, icon, position in COLLECTIONS:
            await catalog.add_category(key, label, position, icon)
        made = 0
        for product in PRODUCTS:
            if not await self._scalar("SELECT 1 FROM marketplace.products WHERE key = :k", k=product["key"]):
                await catalog.create(self.admin, product)
                await catalog.move(self.admin, product["key"], "available")
                made += 1
            presentation: tuple[str, str, bool, str, str | None] = PRESENTATION.get(
                product["key"], ("common", "auto", False, "essentials", None)
            )
            rarity, effect, featured, collection, art = presentation
            current = await self._scalar(
                "SELECT rarity || '|' || poster_effect || '|' || featured::text || '|' || coalesce(icon, '') "
                "FROM marketplace.products WHERE key = :k",
                k=product["key"],
            )
            if current != f"{rarity}|{effect}|{str(featured).lower()}|{art or ''}":
                await catalog.present(
                    self.admin,
                    product["key"],
                    PresentationIn(rarity=rarity, poster_effect=effect, featured=featured, icon=art),
                    collection,
                )
        return f"{made} products published"

    async def purchases(self) -> str:
        purchases = self.platform.marketplace.purchases
        for name, keys in (("admin", OWNED_BY_ADMIN), ("alice", OWNED_BY_ALICE)):
            for key in keys:
                if name in self.people:
                    await purchases.acquire(self.p(name), key, f"demo:{name}:{key}")
        return "owned items in place"

    async def projects(self) -> str:
        marketplace = self.platform.marketplace
        made = 0
        for ref, title, funders, target in PROJECTS:
            project_id = await self._scalar(
                "SELECT id FROM marketplace.projects WHERE proposal_ref = :r", r=ref
            )
            if project_id is not None:
                continue
            project = await marketplace.projects.register(ref, self.people.get("alice"), title)
            await marketplace.transition(self.admin, project.id, "proposal")
            await marketplace.transition(self.admin, project.id, "open", rules=FUNDING_RULES)
            for name, amount in funders.items():
                if name in self.people:
                    await marketplace.fundings.fund(
                        self.p(name), project.id, amount, acknowledged=True, request_key=f"demo:{ref}"
                    )
            if target == "released":
                for state in ("validation", "development", "beta", "released"):
                    await marketplace.transition(self.admin, project.id, state, note="Demo data")
            made += 1
        return f"{made} projects created"

    async def campaign(self) -> str:
        campaigns = self.platform.campaigns
        if await self._scalar("SELECT 1 FROM campaigns.campaigns WHERE key = 'autumn_festival'"):
            return "exists"
        now = utc_now()
        definition = {
            "names": {"en": "Autumn festival", "fr": "Festival d'automne"},
            "timezone": "Europe/Paris",
            "schedule": {
                "start_at": (now - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00"),
                "end_at": (now + timedelta(days=21)).strftime("%Y-%m-%dT00:00:00"),
            },
            "modifiers": [
                {"id": "festival_xp", "value": "xp", "factor": 1.5, "when": {"media_kind": ["movie"]}}
            ],
        }
        await campaigns.definitions.create(self.admin, "autumn_festival", definition)
        await campaigns.reconciler.run()
        return "created and active"

    async def news(self) -> str:
        articles = self.platform.news.articles
        made = 0
        for index, (title, summary, body) in enumerate(ARTICLES):
            if await self._scalar("SELECT 1 FROM news.articles WHERE title = :t LIMIT 1", t=title):
                continue
            row = await articles.create(
                self.admin,
                ArticleInput(title=title, body_md=body, summary=summary, notify_on_publish=index == 0),
            )
            await articles.transition(self.admin, row.id, "publish")
            made += 1
        return f"{made} articles published"

    async def wiki(self) -> str:
        pages = self.platform.wiki.pages
        made = 0
        for slug, title, body in WIKI:
            if await pages.find(slug) is not None:
                continue
            await pages.create(
                self.admin, PageInput(title=title, body_md=body, slug=slug, readable_by_ai=True), publish=True
            )
            made += 1
        return f"{made} pages published"

    async def support(self) -> str:
        support = self.platform.support
        made = 0
        for name, kind, title, description, fields in TICKETS:
            if name not in self.people or await self._scalar(
                "SELECT 1 FROM support.tickets WHERE title = :t LIMIT 1", t=title
            ):
                continue
            await support.tickets.create(self.p(name), TicketRequest(kind, title, description, fields))
            made += 1
        for name, form, values in FEEDBACK:
            marker = next(iter(values.values()))
            if name not in self.people or await self._scalar(
                "SELECT 1 FROM support.feedback_items WHERE payload::text LIKE :m LIMIT 1", m=f"%{marker}%"
            ):
                continue
            await support.feedback.submit(self.p(name), form, dict(values))
            made += 1
        return f"{made} tickets/feedback created"

    async def notifications(self) -> str:
        ref = await self.platform.notifications.send(
            CommunicationRequest(
                category="communications.broadcast",
                template_key="notifications:broadcast.message",
                audience=AllAuthenticated(),
                dedup_key="demo:welcome",
                params={
                    "title": "Welcome to the demo portal",
                    "body": "Explore the Marketplace, the community projects and your progression.",
                },
                source="admin_rule",
                action_url="/progression",
            ),
            caller=self.admin,
        )
        return "broadcast sent" if ref.created else "exists"

    async def leaderboards(self) -> str:
        refreshed = await self.platform.gamification.leaderboards.refresh(force=True)
        return f"{refreshed} boards refreshed"


async def seed_demo(platform: Platform, *, users_file: Path | None = None) -> SeedReport:
    return await DemoSeeder(platform, users_file=users_file).run()
