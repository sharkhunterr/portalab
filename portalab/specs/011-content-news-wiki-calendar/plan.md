# Implementation Plan: Content — News, Wiki, Calendar

**Branch**: `011-content-news-wiki-calendar` | **Date**: 2026-10-01 | **Spec**: `specs/011-content-news-wiki-calendar/spec.md`
**Roadmap**: Phase 5 step 17 *Support / Wiki / Feedback* (Wiki is the knowledge source of 016's diagnosis/precheck; News and Calendar complete the content domains). Builds on 003 (roles `editor`), 006 (maintenance source), 007, 008 (SDK), 010 (categories), 022/004, 026.

## Summary
Three distinct modules — **news** (editorial lifecycle: draft/schedule/publish/feature/archive, categories, audience), **wiki** (versioned Markdown knowledge with safe rendering, history/compare/restore, hierarchy, AI-usable and contextual help pages) and **calendar** (federated, permission-at-source aggregation of dated items owned by other domains, with opt-in reminders) — joined only by `ContentRef`/`LinkResolver`, a shared **sanitized Markdown pipeline** and an asset helper. Notifications, search, AI and maintenance/campaign lifecycles stay with their owners.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: `markdown-it-py` (+ `mdit-py-plugins`), `nh3` (sanitizer), `diff-match-patch` (compare); frontend `mermaid` (strict) · **Storage**: schemas `news`, `wiki`, `calendar`, helper `content`; assets via `core.blobstore` · **Testing**: pytest real PG, XSS corpus, Vitest, Playwright + axe · **Constraints**: no unsafe execution, per-viewer link states, history append-only, calendar owns no lifecycle · **Scale**: ≤ 10⁴ articles/pages, ≤ 10⁵ revisions.

## Constitution Check — PASS
I Product integrity (three distinct domains) · II/XX no second notification/search/AI/event engine; calendar sources owners' data (CD-014 provenance) · III extensible `CalendarSource`/content refs for plugins · VI/VII permission + safe rendering + privacy · IX one domain's failure never blocks others · XII accessible editor/calendar · XIII audit of sensitive content actions. No violations.

## 1. Architecture
```
Editor ─▶ news.ArticleService (state machine, audience, featuring, schedule job) ─▶ MarkdownRenderer ─▶ rendered_html cache ─▶ events ─▶ 010 notify
Editor ─▶ wiki.PageService (base_version check, revisions append-only, tree, tags, links) ─▶ MarkdownRenderer ; HistoryService(compare/restore)
Reader ─▶ GET pages/articles (audience+permission) ─▶ frontend renders sanitized HTML ─▶ POST /content/links/resolve (per-viewer states) ; Mermaid strict
Calendar ─▶ CalendarAggregator ─┬ CalendarSource[news] ┬ [maintenance 006] ┬ [campaigns 014*] ┬ [community 012*] ┬ [deadlines 013/015*]   (parallel, timeout, permission at source)
Reminders ─▶ job at remind_at ─▶ re-fetch item + permission ─▶ 010 send(category calendar.reminder)
Search(008) providers news/wiki · support.knowledge · HelpResolver · assets(blobstore)      (* sources land with their specs)
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `MarkdownRenderer` (`capabilities/content`) | CommonMark+GFM+callouts+code+mermaid placeholders, sanitize, outline, links | markdown-it-py, nh3 | `render()` | raw HTML off; allowlist; versioned cache | XSS corpus tests |
| `AssetService` | upload/sniff/re-encode/serve bound to owner permission | blobstore | API | no external images by default | asset tests |
| `LinkResolver` registry + `/content/links/resolve` | per-viewer link state | domains | batch API | no title leak when forbidden | link-state tests |
| `news.ArticleService` | lifecycle, audience, featuring, revisions, translations | `core.db`, jobs | API | valid transitions only; publish job idempotent | state-machine tests |
| `news.AudienceEvaluator` | roles/groups/permission audience | authz | `can_read()` | server-side; composes with privacy | audience tests |
| `news.Publisher` | publish/archive events, notification request | 010, 007 | internal | dedup `(article, publish_seq)` | idempotency tests |
| `wiki.PageService` | pages, tree, tags, optimistic save, revisions, publish/archive/move | `core.db` | API | `base_version` required; append-only | concurrency tests |
| `wiki.HistoryService` | list/compare/restore | revisions | API | restore = new revision; textual diff markers | compare/restore tests |
| `wiki.KnowledgeProvider` / `HelpResolver` | AI/support/help knowledge | authz | ports | principal-bounded | permission tests |
| `calendar.Aggregator` | fan-out sources, merge, states | sources, 026 | `GET /calendar` | source timeout; no own items | isolation tests |
| `calendar.ReminderService` | opt-in reminders, jobs, re-check | 010, jobs | API/job | stale/cancel handling | reminder tests |
| Frontend | editors, trees, history UI, calendar, link component, mermaid | 022/004/026 | components | a11y; safe rendering | component/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/content-contracts.md`

## 5. Events
Produced (ids/state only): `news.article_published|archived|restored|deleted|featured`, `wiki.page_created|revised|published|archived|restored|deleted`, `calendar.reminder_sent`. Dedup per data-model. Consumers: 010 (publish notifications via `send`, not events), 008 index (providers query live), 017 (optional content stats), 019 automations. Consumed: `maintenance.*`/campaign/community events to refresh reminders; erasure participant (author tombstone). Scheduled publish uses a job with `run_at`; replays do not republish (state check + `publish_seq`).

## 6. Permissions & Security
News: `news.read|create|edit|publish|archive|delete|manage_categories`; Wiki: `wiki.read|edit|publish|delete|history.read`; Calendar: `calendar.read`. Editor base role gets create/edit/publish/archive; Admin all; authors edit own drafts. Sensitive (audited, confirmation for irreversible): publish when configured sensitive, archive, delete (published/archived), wiki delete, restoring beyond N versions. Rendering: raw HTML off, nh3 allowlist, CSP on content pages, `rel` on external links, Mermaid strict, assets re-encoded, external images blocked, comparison/preview use the same sanitizer. AI and automations read content only as the acting principal.

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations — none (external links are plain links; no embeds).

## 9. Error Handling & Resilience
Scheduled publish job crash ⇒ re-claimed, state guard prevents double publish · renderer failure ⇒ save rejected with reason (source retained) / existing cached HTML served · Mermaid failure ⇒ code block fallback · calendar source slow/failing ⇒ `source_state` only, others render · reminder source gone ⇒ cancelled with notice · conflict on wiki save ⇒ 409 + diff · link target forbidden/archived/deleted ⇒ degraded link, never dead-end (FR-027) · notification service down ⇒ publish unaffected (notification retried by 010).

## 10. Observability
Publish job lag, render failures/sanitizer strips (counts), conflict rate, calendar source latency/failure by source, reminder outcomes, broken-link report size; registers `content` with 025 (functional: scheduled-publish lag, calendar sources healthy).

## 11. Testing Strategy
Unit: Markdown corpus (valid features, callouts, tables, code, Mermaid placeholder) and **XSS/security corpus** (script tags, `javascript:`/`data:` URLs, event handlers, SVG, iframe, CSS injection, malformed nesting) through the same pipeline; transitions; audience; featuring limit/order; diff correctness. Integration (real PG): article lifecycle incl. schedule with fake clock; concurrent wiki saves; restore semantics; history permission; per-viewer link resolution; calendar aggregation with failing/slow fake sources; reminders re-check; translations via 026. Security: IDOR on drafts/assets, audience leakage via search/featured/notifications. Frontend: editor preview parity, history compare accessibility (non-color markers), calendar keyboard navigation and type legend. E2E: editor → publish → reader; wiki conflict flow.

## 12. Migration / Versioning
Alembic revisions for `news`, `wiki`, `calendar`, `content`; `renderer_version` bumps trigger lazy re-render (rendered cache is derived; source Markdown authoritative); source Markdown never rewritten by renderer upgrades; contracts semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002/003 (roles), 007, 010 (send/categories), 020, 021, 022/004, 026 (`LocaleContext`, `ContentLocalizer`), 008 (provider SDK). Calendar sources: 006 (maintenance) now; 014/012/013/015 register later. Exposes: `support.knowledge` (016), `KnowledgeProvider` for 018, `ContentRef`/`LinkResolver` to 012/015/016/024, News/Calendar widgets to 009. Concurrency of upload safety shares logic with 016's attachments (extract common sniff/re-encode helper to `core`).

## 14. Implementation Phases
1 Shared renderer/assets/link resolver + security corpus → 2 Wiki core (pages/tree/revisions/optimistic save) → 3 Wiki history/compare/restore → 4 Wiki AI/help/knowledge ports → 5 News core + audience + categories → 6 News schedule/feature/archive/notify → 7 Calendar aggregator + sources (news, maintenance) → 8 Reminders → 9 Translations, search providers, widgets → 10 Hardening/observability.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** OQ-50..54 use plan defaults (research); **product confirmation requested** (deadline sources, Markdown feature set, edit model, audience model, featured limits).
- **R2** Server-rendered HTML + sanitizer is the single trust boundary: mitigated by a mandatory XSS corpus test and CSP; renderer upgrades are tested against the corpus.
- **R3** Mermaid executes in the client; strict mode + isolation reduce but do not eliminate risk — feature flag `content.mermaid.enabled`.
- **R4** Calendar sources for campaigns/community/deadlines are delivered with their specs; initial calendar shows maintenance and News publications.
- **R5** No collaborative editing: acceptable at community scale; conflict UX must be good.
- **R6** History visibility default (editors only) is a policy choice flagged for confirmation.

## Project Structure
```text
backend/src/portalab/{capabilities/content, modules/{news,wiki,calendar}/{service,api,models,...}} · backend/migrations/{news,wiki,calendar,content}/versions/
frontend/src/features/{news,wiki,calendar,content}/
```
