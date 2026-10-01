# Contracts — Content

## Capability `capabilities/content`
- `ContentRef.parse/format` · `LinkResolver` registry: each domain provides `resolve(ref, viewer) -> ResolvedLink{state: ok|forbidden|archived|deleted|unavailable, title?, url?}` (title only when `ok`/`archived` and permitted).
- `MarkdownRenderer.render(md, *, ctx) -> RenderedContent{html, outline, links[], assets[], renderer_version}` (sanitized, raw HTML off, callouts, code, Mermaid placeholders, external-link rules).
- `AssetService.upload(file, owner_ref, actor) -> AssetRef` (sniff/re-encode/limit) and `GET /content/assets/{id}` (read bound to the owning object's permission).
- `CalendarSource` Protocol: `kind` · `label_key` · `async items(range, viewer, ctx) -> CalendarSourceResult{items[CalendarItem], state, as_of}`; `CalendarItem{source_kind, source_id, type (event|maintenance|campaign|community_event|deadline|publication), title, starts_at|date, ends_at?, all_day, reference_tz?, status, url_ref}`.
- `support.knowledge` implementation (wiki) · `HelpResolver.for_context(key, principal)`.

## HTTP (`/api/v1`) — News
| Path | Permission |
|---|---|
| GET `/news?category&cursor` · GET `/news/featured` · GET `/news/{slug}` | `news.read` (default grant) + article audience |
| GET `/news/categories` | `news.read` |
| POST/PATCH `/admin/news/articles[/{id}]` (draft edits) | `news.create` / `news.edit` (own drafts or all per role) |
| POST `/admin/news/articles/{id}/publish|schedule|feature|unfeature|archive|restore` | `news.publish` / `news.archive` (sensitive configurable, audited) |
| DELETE `/admin/news/articles/{id}` | `news.delete` (drafts; archived = sensitive + confirmation) |
| CRUD `/admin/news/categories` | `news.manage_categories` |
## Wiki
| Path | Permission |
|---|---|
| GET `/wiki/tree` · GET `/wiki/pages/{slug}` | `wiki.read` + page audience |
| POST `/wiki/pages` · PUT `/wiki/pages/{id}` (`base_version` required) | `wiki.edit`; 409 `wiki.version_conflict` with diff |
| POST `/wiki/pages/{id}/publish|archive|move` · DELETE | `wiki.publish` / `wiki.delete` (sensitive, confirmation) |
| GET `/wiki/pages/{id}/revisions` · `/revisions/{v}` · `/compare?from&to` | `wiki.history.read` |
| POST `/wiki/pages/{id}/restore` `{version}` | `wiki.edit` (creates new revision) |
| GET `/help?key=` | authenticated (permitted pages only) |
| POST `/content/assets` | `wiki.edit` or `news.edit` (owner permission) |
| POST `/content/links/resolve` (batch refs) | authenticated; returns per-viewer state |
## Calendar
| Path | Permission |
|---|---|
| GET `/calendar?from&to&types&view` | `calendar.read` (default grant); items filtered at source; response includes `source_states` |
| POST/DELETE `/me/calendar/reminders` · GET `/me/calendar/reminders` | self |
Problem codes: `content.unsafe_markdown`, `wiki.version_conflict`, `news.invalid_transition`, `calendar.range_too_large`.

## Frontend
News list/featured/detail + editor (Markdown with live sanitized preview, schedule/feature controls); Wiki tree/page/editor/history/compare; Calendar month/week/list with type legend (icon+label), source-state banner; `<ContentLink>` resolver component; contextual help button (004 slot).

## Integrations provided
Search providers `news`, `wiki` (008) · `support.knowledge` (016) · widgets `news.featured|latest`, `calendar.upcoming` (009) · notification categories `news.published`, `calendar.reminder` (010) · AI knowledge read tools (018) · palette actions/object resolvers (008).
