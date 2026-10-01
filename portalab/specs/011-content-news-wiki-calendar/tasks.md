---
description: "Task list — Content: News, Wiki, Calendar (spec 011)"
---

# Tasks: Content — News, Wiki, Calendar

**Input**: `specs/011-content-news-wiki-calendar/` · **Branch**: `011-content-news-wiki-calendar` · **Roadmap**: Phase 5 step 17 · **Tests**: included.
Abbrev: **`CT/`** = `backend/src/portalab/capabilities/content`, **`NW/`** = `backend/src/portalab/modules/news`, **`WK/`** = `backend/src/portalab/modules/wiki`, **`CL/`** = `backend/src/portalab/modules/calendar`, **`FC/`** = `frontend/src/features`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs/blobstore · `D-002/003` principal/authz (role `editor`), `AuditSink`, `ConfirmationService` · `D-006` maintenance source · `D-007` events · `D-008` search SDK · `D-010` `send`/categories · `D-020` settings · `D-021` retention/erasure · `D-022/004` UI · `D-026` `LocaleContext`, `ContentLocalizer`. Calendar sources for campaigns (014), community events (012), deadlines (013/015) register when those specs land.

## Phase 1: Setup
- [ ] T001 Create `CT/__init__.py`, `NW/`, `WK/`, `CL/` packages (`service,api,models,jobs`), `backend/migrations/{news,wiki,calendar,content}/versions/`, `FC/{news,wiki,calendar,content}/`, `backend/tests/{unit,integration,security}/{news,wiki,calendar,content}/`, `frontend/tests/{unit,e2e}/content/`
- [ ] T002 [P] Add deps (`markdown-it-py`, `mdit-py-plugins`, `nh3`, `diff-match-patch`; frontend `mermaid`) and declare settings (`content.allowExternalImages`, `content.mermaid.enabled`, `news.maxFeatured`, `news.defaultAudience`, `wiki.history.visibility`, `wiki.maxPageBytes`, `calendar.sourceTimeoutMs`, `calendar.maxRangeDays`, `calendar.reminderLeadOptions`) in `{NW,WK,CL}/settings.py`
- [ ] T003 [P] Declare permissions with default role grants (`news.read|create|edit|publish|archive|delete|manage_categories`, `wiki.read|edit|publish|delete|history.read`, `calendar.read`) in `{NW,WK,CL}/permissions.py`; notification categories `news.published`, `calendar.reminder` (010); retention targets and erasure participant for reminders/authors in `{NW,WK,CL}/privacy.py`

## Phase 2: Foundational — shared safe rendering, assets, links
### Tests first
- [ ] T004 [P] Write `backend/tests/security/content/test_markdown_xss_corpus.py`: corpus (script tags, `javascript:`/`data:`/`vbscript:` URLs, event handlers, SVG/MathML payloads, iframes/objects, CSS injection, malformed nesting, HTML in code fences, callout injection) all rendered inert; external links get `rel` + external marker; external images blocked by default; raw HTML disabled
- [ ] T005 [P] Write `backend/tests/unit/content/test_markdown_features.py`: CommonMark + GFM tables/task lists, callouts (note/tip/important/warning/caution), code blocks, Mermaid fence → placeholder with escaped source, outline extraction, internal `portalab://` links collected, deterministic output per `renderer_version`
- [ ] T006 [P] Write `backend/tests/integration/content/test_assets_links.py`: upload sniffing/re-encode/limits; asset readable only with the owning object's permission; batch link resolution returns `ok|forbidden|archived|deleted|unavailable` per viewer without title leak
### Implementation
- [ ] T007 Implement `CT/render.py` (`MarkdownRenderer`), `CT/refs.py` (`ContentRef`, `LinkResolver` registry), `CT/assets.py` (`AssetService`, shared sniff/re-encode helper extracted to `core` for reuse by 016) and routers `POST /content/assets`, `GET /content/assets/{id}`, `POST /content/links/resolve`
- [ ] T008 Implement frontend `FC/content/{SafeHtml,ContentLink,MermaidBlock,MarkdownPreview}.tsx` (sanitized insertion, link state annotation, strict Mermaid with code fallback, accessible callouts with icon+label)
- [ ] T009 Implement `{NW,WK,CL}/models` + Alembic revisions for schemas `news`, `wiki`, `calendar`, `content` (append-only triggers on revisions)

## Phase 3: US3 — Wiki: rich pages, safe rendering (P1) 🎯 MVP
**Independent test**: a page with Markdown, image, links, table, code, Mermaid and callout renders correctly and safely; non-editors cannot edit.
- [ ] T010 [P] [US3] Write `backend/tests/integration/wiki/test_pages.py`: create/read/update with `base_version`; permission matrix (reader/editor/admin); unsafe content inert on read; external vs internal links distinguishable; oversize page rejected
- [ ] T011 [US3] Implement `WK/pages.py` (`PageService` create/read/update, render on save, tags, link extraction to `wiki.page_links`) and routers `GET /wiki/pages/{slug}`, `POST /wiki/pages`, `PUT /wiki/pages/{id}`
- [ ] T012 [US3] Implement frontend `FC/wiki/{PageView,PageEditor}.tsx` (Markdown editor with live sanitized preview, asset upload, accessible toolbar) and optional secret-pattern warning on save (non-blocking)

## Phase 4: US4 — Wiki: history, comparison, restoration (P1)
- [ ] T013 [P] [US4] Write `backend/tests/integration/wiki/test_history.py`: every save appends a revision with author/timestamp; compare two versions with textual added/removed markers (line + word level); restore creates a new revision referencing the restored one; prior revisions untouched; history requires `wiki.history.read`; stale `base_version` ⇒ 409 `wiki.version_conflict` with diff
- [ ] T014 [US4] Implement `WK/history.py` (list, compare via diff-match-patch, restore) and routers `GET /wiki/pages/{id}/revisions[/{v}]`, `GET …/compare`, `POST …/restore`; frontend `FC/wiki/{History,Compare,ConflictResolver}.tsx` with non-color-only change markers

## Phase 5: US5 — Wiki: organization, AI-usable pages, contextual help (P2)
- [ ] T015 [P] [US5] Write `backend/tests/integration/wiki/test_knowledge_help.py`: tree/move/ordering/breadcrumbs; `readable_by_ai` pages only returned to principals who can read them; `HelpResolver.for_context` returns permitted pages only; `support.knowledge` port conformance; broken internal links reported
- [ ] T016 [US5] Implement `WK/tree.py`, `WK/knowledge.py` (`KnowledgeProvider`, `HelpResolver`, FTS `search_vector` update on save), routers `GET /wiki/tree`, `GET /help`, `POST /wiki/pages/{id}/move`, search provider `wiki` (008) and frontend `FC/wiki/{Tree,HelpButton}.tsx` (004 help slot)

## Phase 6: US1 — News: author, publish, feature, archive (P1)
- [ ] T017 [P] [US1] Write `backend/tests/unit/news/test_state_machine.py`: transitions `draft → published|scheduled`, `scheduled → published|draft`, `published → archived`, `archived → published` (restore); invalid transitions rejected; only drafts hard-delete; delete of archived is sensitive
- [ ] T018 [P] [US1] Write `backend/tests/integration/news/test_publication.py` (fake clock): drafts invisible to readers; scheduled publish exactly once at `publish_at` even with duplicate job runs; featuring window and `news.maxFeatured` order/limit; archive removes from discovery; permission matrix; audited sensitive actions
- [ ] T019 [US1] Implement `NW/articles.py` (`ArticleService`, revisions, render, `publish_seq`), `NW/jobs.py` (scheduled publish), routers under `/admin/news/articles/*`, `GET /news`, `GET /news/featured`, `GET /news/{slug}`
- [ ] T020 [US1] Implement frontend `FC/news/{NewsList,FeaturedShelf,ArticleView,ArticleEditor}.tsx` (schedule/feature controls, preview parity, states)

## Phase 7: US2 — News: categories, discovery, notifications (P2)
- [ ] T021 [P] [US2] Write `backend/tests/integration/news/test_audience_notify.py`: category filter; audience (all/roles/groups/permission) enforced for list, detail, search, featured and notifications; publish with notify sends one `news.published` communication to the audience (dedup on replay); no leakage to non-audience
- [ ] T022 [US2] Implement `NW/categories.py` + `/admin/news/categories`, `NW/audience.py`, `NW/notify.py` (010 `send`, dedup `(article, publish_seq)`), search provider `news` (008), widgets `news.featured|latest` (009)

## Phase 8: US6 — Calendar: unified view of dated items (P1)
- [ ] T023 [P] [US6] Write `backend/tests/integration/calendar/test_aggregator.py`: items from fake sources merged by type with links to source records; items the viewer may not see absent; one slow/failing source ⇒ only its `source_state` degraded; range cap; DST/all-day rendering with user tz and first-day-of-week (026)
- [ ] T024 [P] [US6] Write `frontend/tests/e2e/calendar/views.spec.ts`: month/week/list views, keyboard navigation, type legend with icon+text (not color-only), source-state banner, mobile layout
- [ ] T025 [US6] Implement `CL/aggregator.py`, `CalendarSource` registry, built-in sources `news` (scheduled/featured publications) and `maintenance` (006), `GET /calendar`, and frontend `FC/calendar/{CalendarPage,MonthView,WeekView,ListView}.tsx`

## Phase 9: US7 — Calendar: maintenance, campaigns, community events, deadlines, reminders (P2)
- [ ] T026 [P] [US7] Write `backend/tests/integration/calendar/test_reminders.py`: opt-in reminder fires once via 010 `send`; at fire time item re-fetched — changed ⇒ updated notice, removed/forbidden ⇒ cancelled; duplicate job runs safe; deadlines come only from owner sources (none invented); erased with account
- [ ] T027 [US7] Implement `CL/reminders.py` (`calendar.reminders`, jobs, change handling), routers `POST/DELETE/GET /me/calendar/reminders`, `calendar.upcoming` widget (009), and source-registration docs for 012/013/014/015

## Phase 10: US8 — Three domains distinct but interconnectable (P1)
- [ ] T028 [P] [US8] Write `backend/tests/integration/content/test_interconnection.py`: News links Wiki and Calendar items via `ContentRef`; forbidden link shows no title; archived/deleted targets degrade gracefully with no dead end; no FK between schemas; one domain down leaves others rendering; domain lifecycles remain independent
- [ ] T029 [US8] Register `LinkResolver`s for news/wiki/calendar, wire `ContentLink` states in all renderers, and add cross-domain "related items" component `FC/content/RelatedItems.tsx`

## Phase 11: Translations, security hardening & polish
- [ ] T030 [P] Implement translations via 026 `ContentLocalizer` for news/wiki (`article_translations`, `page_translations`, not-translated indication, source language preserved) with tests `backend/tests/integration/content/test_translations.py`
- [ ] T031 [P] Write `backend/tests/security/content/test_authz_idor.py`: draft/unpublished/forbidden content not reachable via ids, slugs, assets, search, featured, calendar or notifications; admin-only operations enforced; sensitive actions audited; AI/knowledge ports principal-bounded
- [ ] T032 [P] Register `content` with Observability (scheduled-publish lag, sanitizer strips, render failures, conflict rate, calendar source health, broken links) in `{NW,WK,CL}/observability.py`; renderer-upgrade lazy re-render job with corpus regression
- [ ] T033 [P] Add all `/news*`, `/admin/news/*`, `/wiki/*`, `/help`, `/content/*`, `/calendar*`, `/me/calendar/*` routes to the permission-matrix test, regenerate OpenAPI client, write `docs/content.md` (Markdown feature set/safety policy, audiences, featuring, calendar source contract)
- [ ] T034 Run `specs/011-content-news-wiki-calendar/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-50..54 defaults)

## Dependencies & Order
Setup → Foundational (shared rendering) → US3 → US4 → US5 → US1 → US2 → US6 → US7 → US8 → Polish. Wiki first because 016 diagnosis/precheck consumes `support.knowledge`; News needs the shared renderer; Calendar sources `news`/`maintenance` need US1 and 006; US8 needs all three resolvers.
**Parallel examples**: T004/T005/T006 · T010 with T017 · T023/T024 · T030/T031/T032/T033.
**MVP**: Phases 1–3 (safe rendering pipeline and Wiki pages) then Phase 6 (News publication).

## Format validation
34 tasks, all checkbox + ID + path; story labels only on story phases.
