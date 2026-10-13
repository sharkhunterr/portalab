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

from portalab.app import demo_economy
from portalab.app.demo_shop import COLLECTIONS, RETIRED, SHOP, definition
from portalab.app.wiring import Platform
from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.notifications import AllAuthenticated, CommunicationRequest
from portalab.capabilities.support import TicketRequest
from portalab.core.authz_port import Principal
from portalab.core.logging import get_logger
from portalab.core.time import utc_now
from portalab.modules.administration.firstrun.service import WizardRequest
from portalab.modules.gamification.achievements.definition import parse_achievement
from portalab.modules.gamification.rules.definition import RuleDefinition
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.services.common import SYSTEM
from portalab.modules.identity.services.credentials import set_password
from portalab.modules.news.articles import ArticleInput
from portalab.modules.wiki.pages import PageInput

log = get_logger("portalab.demo")

MEMBERS = (("alice", "Alice Martin"), ("bruno", "Bruno Lefèvre"), ("chloe", "Chloé Dubois"))

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


# 027: more achievements — media, requests, shop, community, progression (rewards stay modest)
def _count(event: str, count: int) -> list[dict[str, Any]]:
    return [{"kind": "event_count", "event_type": event, "count": count}]


ACHIEVEMENTS |= {
    key: {"category": category, "label": label, "description": about, "icon": icon, "criteria": criteria,
          "rewards": rewards}
    for key, category, label, about, icon, criteria, rewards in (
        ("popcorn_time", "service_usage", "Popcorn time", "Finish your first film or episode.", "popcorn",
         _count("media.playback_finished", 1), [{"value": "xp", "amount": 10}]),
        ("binge_watcher", "service_usage", "Binge-watcher", "Finish 50 films or episodes.", "tv",
         _count("media.playback_finished", 50), [{"value": "coins", "amount": 40}]),
        ("golden_cinephile", "service_usage", "Golden cinephile", "Finish 250 films or episodes.",
         "clapperboard", _count("media.playback_finished", 250), [{"value": "coins", "amount": 150}]),
        ("first_wish", "service_usage", "First wish", "Request a film or a series.", "inbox",
         _count("media.request_created", 1), [{"value": "xp", "amount": 15}]),
        ("wishlist_master", "service_usage", "Wishlist master", "Make 25 media requests.", "gift",
         _count("media.request_created", 25), [{"value": "coins", "amount": 50}]),
        ("bug_hunter", "community", "Bug hunter", "Send three pieces of feedback.", "bug",
         _count("feedback.submitted", 3), [{"value": "contribution", "amount": 3}]),
        ("quest_runner", "progression", "Quest runner", "Complete five quests.", "map",
         _count("quest.completed", 5), [{"value": "coins", "amount": 40}]),
        ("shopaholic", "purchase", "Shopaholic", "Buy ten things in the shop.", "store",
         _count("marketplace.purchase", 10), [{"value": "xp", "amount": 60}]),
        ("big_spender", "purchase", "Big spender", "Buy 25 things in the shop.", "gem",
         _count("marketplace.purchase", 25), [{"value": "coins", "amount": 100}]),
        ("patron", "community", "Patron of the arts", "Fund three community projects.", "handshake",
         _count("project.funding_added", 3), [{"value": "contribution", "amount": 5}]),
        ("stylist", "other", "Stylist", "Change your theme five times.", "palette",
         _count("theme.changed", 5), [{"value": "xp", "amount": 20}]),
        ("decorator", "other", "Interior decorator", "Rearrange your dashboard five times.", "dashboard",
         _count("dashboard.layout_changed", 5), [{"value": "xp", "amount": 20}]),
        ("seeker", "service_usage", "Seeker", "Search the portal twenty times.", "search",
         _count("search.performed", 20), [{"value": "xp", "amount": 20}]),
        ("achievement_hunter", "progression", "Achievement hunter", "Unlock ten achievements.", "trophy",
         _count("achievement.unlocked", 10), [{"value": "coins", "amount": 75}]),
        ("year_in_review", "content", "Year in review", "Open your yearly recap.", "sparkles",
         _count("statistics.wrapped_generated", 1), [{"value": "xp", "amount": 30}]),
        ("loyal", "service_usage", "Loyal", "Sign in on a hundred occasions.", "heart",
         _count("user.signed_in", 100), [{"value": "coins", "amount": 120}]),
        ("level_10", "progression", "Double digits", "Reach level 10.", "medal",
         [{"kind": "level_at_least", "level": 10}], [{"value": "coins", "amount": 100}]),
        ("level_20", "progression", "Living legend", "Reach level 20.", "crown",
         [{"kind": "level_at_least", "level": 20}], [{"value": "coins", "amount": 250}]),
        ("xp_10000", "progression", "Ten thousand", "Earn 10,000 XP.", "zap",
         [{"kind": "value_at_least", "value": "xp", "amount": 10000}], [{"value": "coins", "amount": 150}]),
    )
}  # fmt: skip


# #103: what the portal added since — its own player and reader, casting to a TV, books and audiobooks,
# music, live TV, boosters and requests that come true (a filter keeps to the right kind of play)
def _where(event: str, count: int, **fields: Any) -> list[dict[str, Any]]:
    filters = [{"field": key, "op": "eq", "value": value} for key, value in fields.items()]
    return [{"kind": "event_count", "event_type": event, "filter": filters, "count": count}]


FINISHED = "media.playback_finished"
ACHIEVEMENTS |= {
    key: {"category": category, "label": label, "description": about, "icon": icon, "criteria": criteria,
          "rewards": rewards}
    for key, category, label, about, icon, criteria, rewards in (
        ("private_screening", "service_usage", "Private screening",
         "Watch a film to the end in the portal's player.", "film",
         _where(FINISHED, 1, kind="movie", via="portal"), [{"value": "xp", "amount": 20}]),
        ("home_cinema", "service_usage", "Home cinema",
         "Finish ten films or episodes in the portal's player.", "armchair",
         _where(FINISHED, 10, via="portal"), [{"value": "coins", "amount": 40}]),
        ("big_screen", "service_usage", "Big screen", "Cast a film or an episode to a TV from the portal.",
         "cast", _count("media.cast_started", 1), [{"value": "xp", "amount": 20}]),
        ("projectionist", "service_usage", "Projectionist", "Cast to a TV twenty-five times.", "tv",
         _count("media.cast_started", 25), [{"value": "coins", "amount": 60}]),
        ("page_turner", "service_usage", "Page turner", "Finish a book.", "book-open",
         _where(FINISHED, 1, kind="book"), [{"value": "xp", "amount": 20}]),
        ("reading_nook", "service_usage", "Reading nook", "Read a book to the end in the portal's reader.",
         "glasses", _where(FINISHED, 1, kind="book", via="portal"), [{"value": "xp", "amount": 15}]),
        ("bookworm", "service_usage", "Bookworm", "Finish ten books.", "library",
         _where(FINISHED, 10, kind="book"),
         [{"value": "coins", "amount": 60}, {"value": "contribution", "amount": 1}]),
        ("all_ears", "service_usage", "All ears", "Listen to an audiobook to the end.", "headphones",
         _where(FINISHED, 1, kind="audiobook"), [{"value": "xp", "amount": 20}]),
        ("story_time", "service_usage", "Story time", "Listen to ten audiobooks to the end.", "mic",
         _where(FINISHED, 10, kind="audiobook"), [{"value": "coins", "amount": 60}]),
        ("music_lover", "service_usage", "Music lover", "Listen to fifty songs.", "music",
         _where(FINISHED, 50, kind="track"), [{"value": "xp", "amount": 30}]),
        ("channel_surfer", "service_usage", "Channel surfer", "Tune in to live TV.", "radio",
         _where("media.playback_started", 1, kind="live"), [{"value": "xp", "amount": 10}]),
        ("wish_granted", "service_usage", "Wish granted", "One of your requests becomes available.",
         "sparkles", _count("media.request_available", 1),
         [{"value": "xp", "amount": 15}, {"value": "contribution", "amount": 1}]),
        ("surprise_pack", "purchase", "Surprise pack", "Open a booster.", "package",
         _count("marketplace.booster_opened", 1), [{"value": "xp", "amount": 15}]),
        ("pack_addict", "purchase", "Pack addict", "Open twenty boosters.", "gift",
         _count("marketplace.booster_opened", 20), [{"value": "coins", "amount": 50}]),
        ("lucky_hand", "purchase", "Lucky hand", "Draw a legendary card from a booster.", "dices",
         _where("marketplace.booster_opened", 1, best="legendary"), [{"value": "coins", "amount": 75}]),
    )
}  # fmt: skip

# 027: what some achievements unlock — cosmetics in their spirit, most of them exclusive (out of sale)
ACHIEVEMENTS["completionist"] = {
    "category": "purchase",
    "label": "The Collector",
    "description": "Buy 150 things in the shop — nearly the whole catalog.",
    "icon": "gem",
    "criteria": _count("marketplace.purchase", 150),
    "rewards": [{"value": "coins", "amount": 500}],
}


def _unlock(product: str, kind: str, label: str) -> dict[str, str]:
    return {"product": product, "kind": kind, "label": label}


UNLOCKS: dict[str, list[dict[str, str]]] = {
    "golden_cinephile": [_unlock("title_golden_reel", "title", "Golden reel")],
    "wishlist_master": [_unlock("title_wish_master", "title", "Wish master")],
    "bug_hunter": [_unlock("badge_bug_hunter", "badge", "Bug hunter")],
    "patron": [
        _unlock("badge_patron", "badge", "Patron"),
        _unlock("title_patron", "title", "Patron of the arts"),
    ],
    "big_spender": [_unlock("title_big_spender", "title", "Big spender")],
    "achievement_hunter": [_unlock("badge_achievement_hunter", "badge", "Achievement hunter")],
    "loyal": [_unlock("frame_loyal", "avatar_frame", "Loyal golden frame")],
    "night_owl": [_unlock("banner_live_starfield", "profile_banner", "Animated starry banner")],  # #79
    "level_20": [
        _unlock("level_crown", "level_badge", "Crowned level badge"),
        _unlock("title_living_legend", "title", "Living legend"),
    ],
    "xp_10000": [_unlock("levelup_cinema", "level_up", "Premiere level-up")],
    "completionist": [
        _unlock("badge_completionist", "badge", "The Collector"),
        _unlock("title_completionist", "title", "The Collector"),
    ],
    # #103: exclusive looks and sealed boosters (each its own booster: one is offered only once)
    "private_screening": [_unlock("title_front_row", "title", "Front row")],
    "home_cinema": [_unlock("booster_reserve", "booster", "Reserve booster")],
    "big_screen": [_unlock("badge_big_screen", "badge", "Big screen")],
    "projectionist": [_unlock("title_projectionist", "title", "Projectionist")],
    "bookworm": [_unlock("badge_bookworm", "badge", "Bookworm")],
    "story_time": [_unlock("booster_cosmos", "booster", "Cosmos booster")],
    "music_lover": [_unlock("title_music_lover", "title", "Music lover")],
    "surprise_pack": [_unlock("booster_discovery", "booster", "Discovery booster")],
    "pack_addict": [_unlock("booster_prestige", "booster", "Prestige HD booster")],
    "lucky_hand": [_unlock("badge_lucky_hand", "badge", "Lucky hand")],
}  # fmt: skip
for key, unlocks in UNLOCKS.items():
    ACHIEVEMENTS[key] = {**ACHIEVEMENTS[key], "unlocks": unlocks}

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


PRODUCTS: tuple[dict[str, Any], ...] = tuple(definition(product) for product in SHOP)  # 027: demo_shop

FUNDING_RULES = {"consume_at": "released", "min_funding": 5, "max_funding_per_user": 300}
# #94: open for funding — members fund them with Coins they earned, the demo funds nothing
PROJECTS: tuple[tuple[str, str, str], ...] = (
    ("demo-offline-mode", "Offline mode", "open"),
    ("demo-shared-playlists", "Shared playlists", "open"),
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
        await self._step("first run", self.first_run)
        await self._step("members", self.members)
        await self._step("gamification definitions", self.gamification_definitions)
        await self._step("marketplace catalog", self.catalog)
        await self._step("community projects", self.projects)
        await self._step("campaign", self.campaign)
        await self._step("economy", self.economy)
        await self._step("seasonal campaigns", self.seasonal_campaigns)
        await self._step("quests of the year", self.year_quests)
        await self._step("feedback request", self.feedback_request)
        await self._step("news", self.news)
        await self._step("wiki", self.wiki)
        await self._step("support", self.support)
        await self._step("notifications", self.notifications)
        await self._step("leaderboards", self.leaderboards)
        return self.report

    async def first_run(self) -> str:
        """The Admin was bootstrapped from the command line: close the wizard as that Admin (no step)."""
        wizard = self.platform.administration.first_run
        if await wizard.completed():
            return "already completed"
        await wizard.run(WizardRequest(login="", password=""), existing_admin=self.people["admin"])
        return "completed"

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

    async def _access_permissions(self) -> None:
        """027: the permissions the demo shop's « access » products grant are allowed for such products."""
        marketplace = self.platform.marketplace
        await marketplace.refresh_config()
        wanted = sorted(
            {str(p["payload"]["permission"]) for p in SHOP if p["type"] == "access"}
            | set(marketplace.config.access_allowed_permissions)
        )
        writer = marketplace.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
        if writer and wanted != sorted(marketplace.config.access_allowed_permissions):
            await writer[0].provider.set_global(
                self.admin, "marketplace.access.allowedPermissions", wanted, reason="demo shop"
            )
            await marketplace.refresh_config()

    async def catalog(self) -> str:
        """027: the demo shop (``demo_shop``) — new products are created and published, existing ones are
        revised when their price, texts, contents or level changed (purchases keep their snapshot), then
        their presentation and availability (copies, purchase limit) follow the catalog."""
        from portalab.modules.marketplace.products.definition import AvailabilityIn, PresentationIn

        catalog = self.platform.marketplace.catalog
        await self._access_permissions()
        for key, label, icon, position in COLLECTIONS:
            await catalog.add_category(key, label, position, icon)
        made = revised = 0
        for product in SHOP:
            raw = definition(product)
            exists = await self._scalar("SELECT 1 FROM marketplace.products WHERE key = :k", k=product["key"])
            if not exists:
                await catalog.create(self.admin, raw)
                await catalog.move(self.admin, product["key"], "available")
                made += 1
            if product["type"] == "booster" and exists:
                pass  # #81: its odds and refunds are the administrators' — never seeded back over them
            elif product.get("reward_only"):  # 027: given by an achievement, never sold
                current, _ = await catalog.get(product["key"])
                if current.state == "available":
                    await catalog.move(self.admin, product["key"], "unavailable")
            else:
                current, version = await catalog.get(product["key"])
                wanted = raw["version"]
                stored = {
                    "price_coins": version.price_coins,
                    "names": dict(version.names),
                    "descriptions": dict(version.descriptions),
                    "payload": dict(version.payload),
                    "conditions": list(version.conditions),
                }
                if stored != wanted:
                    await catalog.revise(self.admin, product["key"], wanted)
                    revised += 1
                if product["repeatable"] and not current.repeatable:
                    async with self.database.unit_of_work() as uow:  # seeded before products could repeat
                        await uow.session.execute(
                            text("UPDATE marketplace.products SET repeatable = true WHERE key = :k"),
                            {"k": product["key"]},
                        )
            current, _ = await catalog.get(product["key"])
            presentation = PresentationIn(
                rarity=product["rarity"],
                poster_effect="none",
                featured=product["featured"],
                icon=product["icon"],
                season=product.get("season"),
            )
            if (current.rarity, current.poster_effect, current.featured, current.icon, current.season) != (
                presentation.rarity,
                presentation.poster_effect,
                presentation.featured,
                presentation.icon,
                presentation.season,
            ) or current.category_id is None:
                await catalog.present(self.admin, product["key"], presentation, product["collection"])
            limit = product["limit"] or (None, None)
            if (current.supply, current.limit_count, current.limit_days) != (product["supply"], *limit):
                await catalog.set_availability(
                    self.admin,
                    product["key"],
                    AvailabilityIn(supply=product["supply"], limit_count=limit[0], limit_days=limit[1]),
                    product["level"],
                    product.get("contribution"),  # #59: never drop the contribution minimum
                )
        retired = 0
        for key in RETIRED:
            state = await self._scalar("SELECT state FROM marketplace.products WHERE key = :k", k=key)
            if state in ("available", "unavailable"):
                await catalog.move(self.admin, key, "archived")
                retired += 1
        return f"{made} products published, {revised} revised, {retired} retired"

    async def projects(self) -> str:
        marketplace = self.platform.marketplace
        made = 0
        for ref, title, target in PROJECTS:
            project_id = await self._scalar(
                "SELECT id FROM marketplace.projects WHERE proposal_ref = :r", r=ref
            )
            if project_id is not None:
                continue
            project = await marketplace.projects.register(ref, self.people.get("alice"), title)
            await marketplace.transition(self.admin, project.id, "proposal")
            await marketplace.transition(self.admin, project.id, "open", rules=FUNDING_RULES)
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

    async def economy(self) -> str:
        """027: what earns XP (count and time watched), play streaks and level rewards."""
        gamification = self.platform.gamification
        made = 0
        for key, raw in demo_economy.RULES.items():
            if await self._scalar("SELECT 1 FROM gamification.reward_rules WHERE key = :k LIMIT 1", k=key):
                continue
            rule = await gamification.rules.save(self.admin, key, raw)
            await gamification.rules.publish(self.admin, key, rule.version)
            made += 1
        retired = await self._retire_rules(gamification)
        writer = gamification.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
        await gamification.refresh_config()
        settings = 0
        if writer:
            streak = gamification.config.streak or {}
            if streak.get("event_types") == ["media.playback_finished"] and "min_watched_s" not in streak:
                streak = {}  # #94: the former demo streak (finished plays only) gives way to the new one
            if not streak.get("enabled"):
                await writer[0].provider.set_global(
                    self.admin, "economy.streak", demo_economy.STREAK, reason="demo economy"
                )
                settings += 1
            if not gamification.config.level_rewards:
                await writer[0].provider.set_global(
                    self.admin, "economy.levelRewards", demo_economy.LEVEL_REWARDS, reason="demo economy"
                )
                settings += 1
            await gamification.refresh_config()
        return f"{made} rules, {retired} retired, {settings} settings"

    async def _retire_rules(self, gamification: Any) -> int:
        """#94: a former demo rule still as the demo published it is retired (one an administrator changed
        is left alone)."""
        retired = 0
        for key, former in demo_economy.RETIRED_RULES.items():
            current = await self._scalar(
                "SELECT definition FROM gamification.reward_rules WHERE key = :k AND status = 'active' "
                "ORDER BY version DESC LIMIT 1",
                k=key,
            )
            if not isinstance(current, dict):
                continue
            try:
                same = current.get("event_type") == former["event_type"] and (
                    RuleDefinition.model_validate({**current, "label": ""}).grants
                    == RuleDefinition.model_validate({**former, "label": ""}).grants
                )
            except ValueError:
                same = False
            if same:
                await gamification.rules.retire(self.admin, key)
                retired += 1
        return retired

    async def seasonal_campaigns(self) -> str:
        campaigns = self.platform.campaigns
        made = 0
        for key, raw in demo_economy.campaigns(utc_now().date()).items():
            if await self._scalar("SELECT 1 FROM campaigns.campaigns WHERE key = :k", k=key):
                continue
            await campaigns.definitions.create(self.admin, key, raw)
            made += 1
        if made:
            await campaigns.reconciler.run()
        return f"{made} campaigns created"

    async def year_quests(self) -> str:
        gamification = self.platform.gamification
        made = 0
        for key, raw in demo_economy.quests(utc_now().date()).items():
            if await self._scalar("SELECT 1 FROM gamification.quests WHERE key = :k LIMIT 1", k=key):
                continue
            await gamification.quests.save(self.admin, key, raw)
            made += 1
        return f"{made} quests created"

    async def feedback_request(self) -> str:
        definitions = self.platform.support.definitions
        request = demo_economy.FEEDBACK_REQUEST
        if await self._scalar("SELECT 1 FROM support.feedback_forms WHERE key = :k", k=request["key"]):
            return "exists"
        now = utc_now()
        await definitions.save_form(
            self.admin,
            request["key"],
            request["kind"],
            request["label"],
            request["fields"],
            True,
            description=request["description"],
            icon=request["icon"],
            requested=True,
            opens_at=now - timedelta(days=1),
            closes_at=now + timedelta(days=21),
        )
        return "created"

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
        featured = 0
        if not await self._scalar("SELECT 1 FROM news.articles WHERE featured_from IS NOT NULL LIMIT 1"):
            for priority, (title, _, _) in enumerate(ARTICLES[:2]):  # a hero and a side article
                article_id = await self._scalar(
                    "SELECT id FROM news.articles WHERE title = :t AND status = 'published' LIMIT 1", t=title
                )
                if article_id is not None:
                    await articles.feature(self.admin, article_id, None, None, len(ARTICLES) - priority)
                    featured += 1
        return f"{made} articles published, {featured} featured"

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
