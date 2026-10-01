# Data Model — Content (schemas `news`, `wiki`, `calendar`; shared helpers in `capabilities/content`)

Cross-module references are opaque `ContentRef` strings (`portalab://news/<id>`, `portalab://wiki/<id>`, `portalab://calendar/<kind>/<id>`); FKs only intra-module or to `identity.users(id)`.

## news
- **news.categories**: `id` · `key` unique · `label_key`/`name` · `position` · `enabled`.
- **news.articles**: `id` UUIDv7 · `slug` unique · `language` · `title` · `summary` · `body_md` · `rendered_html` · `renderer_version` · `category_id` FK · `author_id` FK · `status` (`draft|scheduled|published|archived`) · `audience` jsonb (`{mode: all|roles|groups|permission, refs[]}`) · `publish_at` null · `published_at` null · `archived_at` null · `featured_from` null · `featured_until` null · `feature_priority` int · `notify_on_publish` bool · `publish_seq` int · `version` · `created_at` · `updated_at`.
- **news.article_revisions** (append-only): `article_id` · `version` · snapshot `title/summary/body_md` · `author_id` · `changed_at`.
- **news.article_translations**: `article_id` · `language` · `title` · `summary` · `body_md` · `rendered_html` · `state` (`translated|machine_draft`) · unique `(article_id, language)` (registered with 026).

## wiki
- **wiki.pages**: `id` · `slug` unique · `parent_id` FK self null · `position` · `status` (`draft|published|archived`) · `current_version` int · `audience` jsonb · `readable_by_ai` bool · `help_keys` text[] · `search_vector` tsvector (generated on revision save) · `created_by` FK · `created_at` · `updated_at`.
- **wiki.revisions** (append-only): `page_id` FK · `version` · `title` · `body_md` · `rendered_html` · `renderer_version` · `author_id` FK · `change_note` · `restored_from_version` null · `created_at`. PK `(page_id, version)`.
- **wiki.page_tags**: `page_id` · `tag`. **wiki.page_links** (derived): `from_page_id` · `target_ref` · for backlinks/broken-link report.
- **wiki.page_translations**: as news (per language revision pointer).

## calendar
- **calendar.reminders**: `id` · `user_id` FK · `source_kind` · `source_id` (opaque) · `remind_at` (UTC) · `lead_minutes` · `status` (`scheduled|sent|cancelled|stale`) · `last_snapshot_hash` · unique `(user_id, source_kind, source_id, lead_minutes)`.
- No item tables: items are fetched live from `CalendarSource`s.

## shared
- **content.assets** (in `capabilities/content` helper schema `content`): `id` · `owner_ref` · `blob_key` · `content_type` (sniffed) · `sha256` · `size` · `uploaded_by` FK · `created_at`.

## Settings (declared into 020)
`content.allowExternalImages` (false), `content.mermaid.enabled` (true), `news.maxFeatured` (3), `news.defaultAudience`, `wiki.history.visibility`, `wiki.maxPageBytes`, `calendar.sourceTimeoutMs`, `calendar.maxRangeDays`, `calendar.reminderLeadOptions`.

## Events (via 007; ids/state only)
News: `news.article_published` (dedup `(article_id, publish_seq)`), `news.article_archived|restored|deleted|featured`. Wiki: `wiki.page_created|revised|published|archived|restored|deleted` (dedup `(page_id, version)`). Calendar: `calendar.reminder_sent` (dedup `(reminder_id)`). Consumed: `maintenance.*`, `campaign.*`, `community.event_*`, deadline source changes (reminder re-evaluation), erasure participant calls (author tombstone).

## Privacy / retention
Content is non-personal except author refs (tombstone-safe). Revisions retained per policy (not public; history requires permission). Reminders are `activity` personal data (erased with account).
