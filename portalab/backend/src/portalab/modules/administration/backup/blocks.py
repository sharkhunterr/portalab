"""What an administrator may choose to bring from a backup into a new portal (issue 392).

A **block** is a part of the portal an administrator ticks or not: its schemas, its settings (by the module
that owns them, in ``config.settings``), its data folders, and the blocks it needs. The accounts and their
roles, the portal's own state and its business events always come (``ALWAYS``): the Admin account is always
brought, a portal without one could not be signed into.

Without the **members** block, only the Admin's account comes. What pointed at another member then follows
the schema's own word (``ON DELETE``) or, where a member is named without a foreign key, ``MEMBER_COLUMNS``:

* ``drop``     — a member's own row (a balance, a session, a purchase, a play): left out with them;
* ``reassign`` — what a member made or decided (an automation, a page, a product): handed to the Admin.

Every schema belongs to one block or to ``ALWAYS``, every module owning settings too, and every column naming
a member without a foreign key is declared here: ``tests/integration/admin/test_backup_blocks.py`` fails
otherwise, so a new module ships sorted.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

Policy = Literal["drop", "reassign"]

MEMBERS = "members"


@dataclass(frozen=True, slots=True)
class Block:
    key: str
    schemas: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()  # the owners of its settings (``module:<name>``)
    folders: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    # what the arrival wizard counts for it: label → table (rows read in the archive's description)
    counts: dict[str, str] = field(default_factory=dict)


BLOCKS: tuple[Block, ...] = (
    Block(
        "settings",
        schemas=("i18n", "ui", "privacy", "search", "shell"),
        modules=("i18n", "ui", "privacy", "search", "shell", "identity", "observability", "events"),
    ),
    Block(MEMBERS, folders=("blobs/avatars",), counts={"members": "identity.users"}),
    Block(
        "services",
        schemas=("connectors",),
        modules=("connectors",),
        counts={"services": "connectors.services"},
    ),
    Block("notifications", schemas=("notify",), modules=("notifications",)),
    Block(
        "media",
        schemas=("media", "requests"),
        modules=("media", "requests"),
        folders=("blobs/media", "blobs/media-metadata"),
        needs=("services",),
        counts={"requests": "media.requests"},
    ),
    Block("statistics", schemas=("stats",), modules=("statistics",), needs=("media",)),
    Block(
        "automations",
        schemas=("automations",),
        modules=("automations",),
        needs=("services",),
        counts={"automations": "automations.automations"},
    ),
    Block(
        "content",
        schemas=("content", "wiki", "news", "calendar", "community", "support"),
        modules=("content", "wiki", "news", "calendar", "community", "support"),
        folders=("blobs/content",),
        counts={"pages": "wiki.pages", "articles": "news.articles"},
    ),
    Block(
        "gamification",
        schemas=("gamification", "campaigns", "games", "cards"),
        modules=("gamification", "campaigns", "games", "cards"),
        folders=("blobs/cards",),
        counts={"quests": "gamification.quests"},
    ),
    Block(
        "marketplace",
        schemas=("marketplace",),
        modules=("marketplace",),
        needs=("gamification",),
        counts={"products": "marketplace.products"},
    ),
    Block(
        "look",
        schemas=("visuals", "dashboard"),
        modules=("visuals", "dashboard"),
        folders=("visuals",),
        counts={"packs": "visuals.packs"},
    ),
    Block("plugins", schemas=("plugins",), modules=("plugins",), folders=("plugins",)),
    Block("assistant", schemas=("ai",), modules=("ai",)),
    Block("health", schemas=("health",), modules=("health",)),
    Block("history", schemas=("audit", "obs")),  # only in an archive saved with its technical history
)

# always brought: the accounts and roles (the Admin's at least), the portal's own state, its business events,
# and the settings store — its rows then sorted by the module owning each key (``SETTINGS_TABLES``)
ALWAYS: tuple[str, ...] = ("identity", "authz", "admin", "events", "core", "config")
ALWAYS_MODULES: tuple[str, ...] = ("administration", "authz")
SETTINGS_TABLES: tuple[str, ...] = ("config.settings", "config.setting_history", "config.policies")

BY_KEY = {block.key: block for block in BLOCKS}

# members named without a foreign key (the tables saved; the transient ones never travel)
MEMBER_COLUMNS: dict[tuple[str, str], Policy] = {
    ("events.events", "actor_user_id"): "reassign",
    ("wiki.page_translations", "updated_by"): "reassign",
    ("wiki.revisions", "author_id"): "reassign",
    ("support.ticket_history", "actor_id"): "reassign",
    ("gamification.reward_rules", "created_by"): "reassign",
    ("gamification.streak_days", "user_id"): "drop",
    ("gamification.freeze_grants", "user_id"): "drop",
    ("gamification.boosts", "user_id"): "drop",
    ("gamification.transactions", "actor_user_id"): "reassign",
    ("marketplace.requests", "user_id"): "drop",
    ("marketplace.requests", "decided_by"): "reassign",
    ("marketplace.reserve_seen", "user_id"): "drop",
    ("marketplace.projects_seen", "user_id"): "drop",
    ("media.activity_daily", "user_key"): "drop",
    ("media.rescues", "user_id"): "drop",
    ("media.radio_credits", "user_id"): "drop",
    ("media.book_positions", "user_id"): "drop",
    ("media.radio_sittings", "user_id"): "drop",
    ("news.article_revisions", "author_id"): "reassign",
    ("news.newsletter_editions", "created_by"): "reassign",
    ("notify.announcements", "created_by"): "reassign",
    ("campaigns.versions", "created_by"): "reassign",
    ("campaigns.activation_log", "actor_user_id"): "reassign",
    ("campaigns.open_intervals", "actor_user_id"): "reassign",
    ("automations.approvals", "decided_by"): "reassign",
    ("authz.grants", "created_by"): "reassign",
    ("authz.user_roles", "granted_by"): "reassign",
    ("authz.user_groups", "granted_by"): "reassign",
    ("authz.confirmations", "principal_user_id"): "drop",
    ("config.settings", "updated_by"): "reassign",
    ("config.setting_history", "actor_id"): "reassign",
    ("config.policies", "set_by"): "reassign",
    ("audit.audit_entries", "actor_user_id"): "reassign",
    ("visuals.scene_bindings", "bound_by"): "reassign",
    ("support.feedback_items", "reviewed_by"): "reassign",
    ("support.feedback_conversions", "converted_by"): "reassign",
    ("connectors.sync_runs", "triggered_by"): "reassign",
    ("gamification.anomaly_flags", "reviewed_by"): "reassign",
    ("gamification.withheld", "reviewed_by"): "reassign",
    ("plugins.purges", "requested_by"): "reassign",
    ("privacy.visibility_policies", "set_by"): "reassign",
    ("privacy.visibility_policies", "removed_by"): "reassign",
    ("automations.versions", "published_by"): "reassign",
    ("admin.extension_toggles", "changed_by"): "reassign",
    ("admin.first_run", "completed_by"): "reassign",
}

# members' rows whose member is only a hash: all left out without the members
MEMBER_TABLES: tuple[str, ...] = ("stats.members",)

# rows pointing at another row without a foreign key: left out when it is
REFERENCES: dict[tuple[str, str], str] = {
    ("marketplace.refunds", "ownership_id"): "marketplace.ownerships",
    ("marketplace.requests", "ownership_id"): "marketplace.ownerships",
}

# a foreign key to a member names who made or decided something: handed to the Admin
_REASSIGNED = {
    "created_by",
    "updated_by",
    "uploaded_by",
    "installed_by",
    "approved_by",
    "granted_by",
    "validated_by",
    "resolved_by",
    "recognized_by",
    "changed_by",
    "decided_by",
    "author_id",
    "author_user_id",
    "actor_id",
    "actor_user_id",
    "owner_user_id",
    "moderator_id",
    "recognizer_id",
    "organizer_id",
    "proposer_id",
    "submitter_id",
    "assignee_id",
    "requester_id",
    "requester_user_id",
}


def foreign_key_policy(column: str, on_delete: str) -> Policy:
    """A foreign key to a member: what the schema deletes with the member is theirs; otherwise, who made or
    decided something is handed to the Admin, and any other row (named ``user_id``…) is the member's."""
    if on_delete == "c":
        return "drop"
    return "reassign" if column in _REASSIGNED else "drop"


@dataclass(frozen=True, slots=True)
class Selection:
    """The blocks chosen, closed over what they need; ``None`` blocks means everything (as before 392)."""

    blocks: frozenset[str]

    @property
    def members(self) -> bool:
        return MEMBERS in self.blocks

    def keeps_table(self, table: str) -> bool:
        schema = table.split(".", 1)[0]
        if schema in ALWAYS:
            return True
        block = block_of_schema(schema)
        return block is not None and block in self.blocks

    def keeps_folder(self, folder: str) -> bool:
        block = block_of_folder(folder)
        return block is None or block in self.blocks

    def keeps_setting_owner(self, owner: str | None) -> bool:
        if (owner or "").startswith("plugin:"):
            return "plugins" in self.blocks
        module = (owner or "").removeprefix("module:")
        if module in ALWAYS_MODULES:
            return True
        block = block_of_module(module) or "settings"  # an undeclared key: the portal's settings
        return block in self.blocks


def block_of_schema(schema: str) -> str | None:
    if schema.startswith("plugin_"):
        return "plugins"
    return next((b.key for b in BLOCKS if schema in b.schemas), None)


def block_of_module(module: str) -> str | None:
    return next((b.key for b in BLOCKS if module in b.modules), None)


def block_of_folder(folder: str) -> str | None:
    return next((b.key for b in BLOCKS if folder in b.folders), None)


def needed(blocks: Iterable[str]) -> dict[str, list[str]]:
    """Every block the chosen ones need, each with the chosen blocks that need it."""
    reasons: dict[str, list[str]] = {}
    pending = [b for b in blocks if b in BY_KEY]
    seen = set(pending)
    while pending:
        current = pending.pop()
        for dependency in BY_KEY[current].needs:
            reasons.setdefault(dependency, []).append(current)
            if dependency not in seen:
                seen.add(dependency)
                pending.append(dependency)
    return reasons


def close(blocks: Iterable[str]) -> Selection:
    """The blocks chosen and everything they need; an unknown block is refused."""
    chosen = set(blocks)
    unknown = chosen - set(BY_KEY)
    if unknown:
        raise ValueError(f"unknown blocks: {sorted(unknown)}")
    return Selection(frozenset(chosen | set(needed(chosen))))


def described(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The blocks an archive offers, for the arrival wizard: what each needs and holds (from the rows its
    description counts). A block whose tables are not in the archive (the technical history saved without
    it) is not offered."""
    rows = {t["name"]: int(t.get("rows", 0)) for t in manifest.get("tables", [])}
    offered = []
    for block in BLOCKS:
        saved = any(block_of_schema(name.split(".", 1)[0]) == block.key for name in rows)
        if not (saved or block.key == MEMBERS or block.modules):
            continue
        offered.append(
            {
                "key": block.key,
                "needs": list(block.needs),
                "counts": {label: rows.get(table, 0) for label, table in block.counts.items()},
            }
        )
    return offered
