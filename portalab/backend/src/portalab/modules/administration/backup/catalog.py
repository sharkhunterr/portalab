"""What a backup holds (issue 247): every table and data folder of the portal is sorted into

* ``data`` — always saved: members, settings, services, content, play, media links and history…;
* ``history`` — saved on request: the technical history (audit, metrics, logs, samples, technical events);
* ``media`` — saved on request (on by default): the media images fetched from the services;
* ``transient`` — never saved: queues, sessions, caches and counters the portal rebuilds.

Each schema is declared here with its default, then the tables apart from it; a schema nobody declared fails
the test (``tests/unit/admin/test_backup_catalog.py``), so a new module is sorted before it ships — and a new
table in a declared schema follows its schema (saved, unless said otherwise here). A plugin's schema
(``plugin_<key>``) is data.
"""

from typing import Literal

Category = Literal["data", "history", "media", "transient"]

SCHEMAS: dict[str, Category] = {
    "admin": "data",
    "ai": "data",
    "audit": "history",
    "authz": "data",
    "automations": "data",
    "calendar": "data",
    "campaigns": "data",
    "cards": "data",
    "community": "data",
    "config": "data",
    "connectors": "data",
    "content": "data",
    "core": "transient",
    "dashboard": "data",
    "events": "data",
    "games": "data",  # issue 265: the games played, the parties, the challenges
    "gamification": "data",
    "health": "data",
    "i18n": "data",
    "identity": "data",
    "marketplace": "data",
    "media": "data",
    "news": "data",
    "notify": "data",
    "obs": "history",
    "plugins": "data",
    "privacy": "data",
    "search": "data",
    "shell": "data",
    "stats": "data",
    "support": "data",
    "ui": "data",
    "visuals": "data",
    "wiki": "data",
}

TABLES: dict[str, Category] = {
    # rebuilt or meaningless elsewhere: sessions, throttles, queues, cursors of caches, epochs
    "events.deliveries": "transient",
    "events.dedup_keys": "transient",
    "events.quarantine": "transient",
    "events.replay_runs": "transient",
    "identity.sessions": "transient",
    "identity.login_throttle": "transient",
    "identity.oidc_logins": "transient",
    "identity.export_jobs": "transient",
    "automations.dedup_windows": "transient",
    "connectors.discovery_candidates": "transient",
    "shell.contribution_errors": "transient",
    "shell.epochs": "transient",
    "visuals.registry_epoch": "transient",
    "i18n.missing_key_stats": "transient",
    "media.activity_dirty_days": "transient",
    "media.task_progress": "transient",
    "notify.email_outbox": "transient",  # never send the former portal's e-mails again
    "plugins.error_stats": "transient",
    "search.index_state": "transient",  # the index is built again
    # the covers fetched from the services go with their files: left out, they are fetched again
    "media.images": "media",
    # the technical history: saved on request
    "health.health_samples": "history",
    "health.infra_samples": "history",
    "health.health_rollups": "history",
    "health.state_history": "history",
    "health.recent_errors": "history",
    "connectors.sync_runs": "history",
    "connectors.compatibility_checks": "history",
    "plugins.network_calls": "history",
    "privacy.retention_runs": "history",
    "stats.rebuild_runs": "history",
}

# a table holding both: its rows split by a condition — (data rows, history rows)
SPLIT: dict[str, tuple[str, str]] = {
    "events.events": ("retention_class = 'business'", "retention_class <> 'business'"),
}

FOLDERS: dict[str, Category] = {
    "blobs/avatars": "data",
    "blobs/content": "data",
    "blobs/cards": "media",  # the cards' images: fetched from the services, cut out, looked for again
    "blobs/media": "media",
    "blobs/media-metadata": "media",
    "cards": "transient",  # the cards' models (downloaded again when needed)
    "visuals": "data",
    "plugins": "data",
    "plugins-run": "transient",
    "backups": "transient",
}


def category_of(table: str) -> Category | None:
    """``schema.table`` → its category; ``None`` for a schema nobody declared."""
    if table in TABLES:
        return TABLES[table]
    schema = table.split(".", 1)[0]
    if schema.startswith("plugin_"):
        return "data"
    return SCHEMAS.get(schema)


def folder_category(folder: str) -> Category:
    """A data folder (``blobs/avatars``, ``visuals``…) → its category; one nobody declared is saved."""
    return FOLDERS.get(folder, "data")
