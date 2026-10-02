# Search providers (spec 008)

Global search is **federated**: each domain module (or plugin) registers a `SearchProvider` that queries
**its own tables** with the principal's permission and the domain's visibility rules applied *inside the
query*. The search module only fans out, applies time budgets, merges groups and never stores domain data.

## Contract (`portalab.capabilities.search`)

| Member | Meaning |
| --- | --- |
| `kind` | group key (`wiki`, `tickets`…; plugins: `plugin:<key>`) |
| `label_key` | catalog key of the group label (`search.kind.<kind>` in the `search` namespace) |
| `required_permission` | the coordinator never calls a provider whose permission the principal lacks |
| `facets()` | filters the provider understands (`FacetDef(key, label_key, kind, values)`) |
| `search(query, principal, ctx, *, limit, cursor)` | `ProviderResult(items, state, next_cursor, facets)` |
| `hydrate(ids, principal)` | items for ids the principal may see **now** (semantic candidates, object refs) |
| `documents(since)` *(optional, `Indexable`)* | texts for the semantic index (ids + vectors only are stored) |

Rules:

- scope by principal in the query — the coordinator's kind-level check is not enough; counts and facets
  only cover permitted items; a forbidden item never shows up, not even as a count;
- return snippets as `snippet(text, query.terms)` segments (plain text + hit flags, never markup);
- bind the query only as a parameter (`text_match`, `text_rank`, `websearch()` / `fts_match()` helpers in
  `portalab.capabilities.search.fts`); for large tables add a generated `search_vector` column with
  `tsvector_ddl()` in your migration;
- never log or publish the query text;
- answer within the budget (`search.providerTimeoutMs`, default 1500 ms) — a slow provider shows as
  `unavailable` without affecting the others.

Register it from your module (owner-tagged, so a disabled plugin's provider disappears with it):

```python
from portalab.capabilities.search import default_search
default_search.register(MyProvider(...), owner="module:wiki")
default_search.register_resolver(MyTicketResolver(...), owner="module:support")  # "#123" references
```

A starting point lives in `modules/search/providers/_template.py`.

## Conformance kit

```python
from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit

class TestWikiProvider(SearchProviderContractKit):
    async def make_world(self) -> ProviderWorld:
        return ProviderWorld(provider, allowed_principal, denied_principal, "matching term", hide=make_private)
```

It checks permission at source (also in `hydrate`), immediate visibility changes, plain-text snippets,
limits and clean cancellation. `tests/contract/search/test_domain_coverage.py` lists the domains expected
to register a provider; each owning spec turns its line green.

## Palette actions and object references

- Commands come from 004 `NavigationContribution(kind="command")` with `sensitivity` and
  `confirmation_required`; page-specific actions are `ActionDef(..., context_route="/tickets/")`.
- The palette only launches: sensitive actions are confirmed and audited by the owning endpoint
  (`ConfirmationService` token, spec 003).
- `ObjectResolver.resolve(ref, principal)` returns `None` both for "unknown" and "not allowed".

## Semantic search (optional)

Needs pgvector in PostgreSQL and an `EmbeddingProvider` (`search.embedding` capability, none by default),
plus `search.semantic.enabled`. Without them the API reports `semantic: "unavailable"` and lexical
matching continues. `POST /api/v1/admin/search/reindex` (permission `search.manage`, audited) queues
`search.index` jobs; `GET /api/v1/admin/search/status` shows index state.
