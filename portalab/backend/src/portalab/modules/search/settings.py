"""Search settings (T002), declared to Administration (CD-011); bound to ``SearchConfig`` at start-up."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:search"
HISTORY_ENABLED = "search.historyEnabled"


@dataclass(frozen=True, slots=True)
class SearchConfig:
    provider_timeout_ms: int = 1500
    max_results_per_group: int = 10
    max_query_length: int = 256
    history_retention_days: int = 90
    history_max_entries: int = 50
    semantic_enabled: bool = False
    semantic_embedding_provider: str = ""
    semantic_top_k: int = 50
    rate_limit_per_minute: int = 60


SETTINGS: dict[str, str] = {
    "provider_timeout_ms": "search.providerTimeoutMs",
    "max_results_per_group": "search.maxResultsPerGroup",
    "max_query_length": "search.maxQueryLength",
    "history_retention_days": "search.historyRetentionDays",
    "history_max_entries": "search.historyMaxEntries",
    "semantic_enabled": "search.semantic.enabled",
    "semantic_embedding_provider": "search.semantic.embeddingProvider",
    "semantic_top_k": "search.semantic.topK",
    "rate_limit_per_minute": "search.rateLimitPerMinute",
}

_DESCRIPTIONS = {
    "provider_timeout_ms": "Time budget (ms) of each search source; a slower source shows as unavailable.",
    "max_results_per_group": "Results shown per result group (type).",
    "max_query_length": "Maximum length of a search query (characters).",
    "history_retention_days": "Days a user's search history is kept.",
    "history_max_entries": "Search history entries kept per user (most recent).",
    "semantic_enabled": "Meaning-based (semantic) search, when an embedding provider is installed.",
    "semantic_embedding_provider": "Embedding provider used for semantic search (empty: none).",
    "semantic_top_k": "Semantic candidates retrieved before permission checks.",
    "rate_limit_per_minute": "Searches allowed per user and minute.",
}


def declare_search_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = SearchConfig()
    for field, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, field)
            declare(
                scope="global",
                key=key,
                schema=type(default),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[field],
            )
    if HISTORY_ENABLED not in known:
        declare(
            scope="global",
            key=HISTORY_ENABLED,
            schema=bool,
            default=True,
            user_overridable=True,
            owner=OWNER,
            description="Keep my search history (private to me).",
        )


declare_search_settings()
