# Content: News, Wiki, Calendar (spec 011)

Three distinct modules — **news** (editorial lifecycle), **wiki** (versioned knowledge) and **calendar**
(federated view of other domains' dated items) — plus the **content** helper (safe assets, link resolution,
render preview). They are joined only by `ContentRef` (`portalab://<kind>/<id>`) and per-viewer link
resolution, never by foreign keys.

## Markdown feature set and safety policy

One server-side pipeline (`portalab.capabilities.content.render`) renders every article, page, preview
and comparison: CommonMark + GFM tables, strikethrough and task lists, GitHub-style callouts
(`> [!NOTE]`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`), fenced code and `mermaid` fences.

- **Raw HTML is disabled**; the output is sanitized by `nh3` with a strict allowlist (no script, style,
  iframe, object, SVG/MathML, forms, event handlers; `style` only for table alignment).
- Links: `http(s)`, `mailto`, relative paths and `portalab://` refs only; external links get
  `rel="noopener noreferrer nofollow external"` and a visible marker; `javascript:`, `data:`,
  protocol-relative and other schemes lose their target.
- Images: only portal assets (`![alt](portalab-asset:<id>)`), uploaded through `POST /content/assets`,
  sniffed by magic bytes and re-encoded (metadata stripped) by the shared `core.uploads` helper; external
  images are blocked unless `content.allowExternalImages` is on.
- Mermaid fences are inert placeholders rendered client-side in **strict** mode on demand; a failing diagram
  stays visible as code. `content.mermaid.enabled` turns diagrams off.
- The XSS corpus test (`tests/security/content/test_markdown_xss_corpus.py`) must pass for any renderer
  change; `RENDERER_VERSION` bumps re-render caches lazily (the Markdown source is authoritative).
- Saving text that looks like a password or key shows a non-blocking warning.

## Links between domains

Authors write `[text](portalab://wiki/<slug-or-id>)`. At display time the page batch-resolves the refs
(`POST /content/links/resolve`) **for the viewer**: `ok` (link + title), `archived` (link + label),
`forbidden` (no link, no title), `deleted` / `unavailable` (no link, label) — never a dead end. Domains
register a `LinkResolver` (`portalab.capabilities.content`); plugins do the same, owner-tagged.

## News

`draft → published` or `draft → scheduled → published` (job at `publish_at`, idempotent: state check +
`publish_seq`, plus a one-minute sweep), `published → archived → published`, `scheduled → draft`;
deleting is a tombstone (a published article must be archived first; deleting an archived one needs a
confirmation). Audience: everyone (`all`), some roles, or holders of a permission — enforced on list,
detail, featured, search, calendar, links and notifications. Featuring is a window evaluated at read time,
capped by `news.maxFeatured` (3) and ordered by priority then recency. Publishing with "notify" sends a
`news.published` communication per audience target (010). Automation action `content.publish` runs as the
rule's author.

## Wiki

Pages are saved with the `base_version` the editor started from: a stale base answers 409
`wiki.version_conflict` with a server-side diff. Every save appends a revision (append-only, only an erased
author may be tombstoned); compare shows line and word changes with textual markers; restoring creates a
new revision referencing the restored one. History requires `wiki.history.read` (editors and support by
default; `wiki.history.visibility = readers` widens it). Pages carry `readable_by_ai` and `help_keys`:
`support.knowledge` and AI tools only see pages the asking user may read (and, for AI, marked readable);
`GET /help?key=` feeds the header help entry (route `/services/<id>` → key `services.detail`).

### Portalab's member guide (issue 457)

`docs/member-guide/<language>/*.md` (a header — `slug`, `title`, `position`, `parent`, `help_keys`, `tags` —
then Markdown) and its screenshots `docs/member-guide/images/<language>/<name>.jpg` are copied into the image
(`/app/guide`, else `PORTALAB_GUIDE_DIR`, else the repository's folder). `modules/wiki/guide.py`
(`GuideSync`) runs at each start and when `wiki.guide.enabled` changes, in the background, under an advisory
lock: each page becomes one wiki page whose source is English, the other languages its translations
(`updated_by` NULL); `![alt](shot:<name>)` becomes `![alt](portalab-guide:<language>/<name>)`, rendered as
`/api/v1/wiki/guide/shots/<language>/<name>.jpg` (wiki readers, names validated, never outside the folder);
« Coins » becomes the site's currency. A page is the guide's while every revision carries the change note
`Portalab member guide` (or `Guide du membre`, the hand import of `scripts/wiki_import.py`, adopted);
otherwise it is its administrator's and never written again. `wiki.guide_pages` remembers what the guide
installed, what it removed (switched off) and what an administrator deleted (`dismissed`, not brought back
until the guide is switched off and on). Pages and the tree take `?lang=` — the interface sends the member's
language.

Screenshots: `node scripts/guide_shots.mjs docs/member-guide/shots --language <en|fr> --names
deploy/secrets/shot_names.json --out docs/member-guide/images/<language> …` — with `--names`, every shot
blurs members' faces and replaces the real names listed in that file (kept out of the repository).

## Calendar source contract

The calendar owns no item. A domain registers a `CalendarSource`:

```python
class MySource:
    kind = "community"
    label_key = "community:calendar.source"
    required_permission = "community.read"  # optional: the whole source is skipped otherwise

    async def items(self, start, end, viewer, ctx) -> CalendarSourceResult: ...  # permission applied here
    async def item(self, source_id, viewer) -> CalendarItem | None: ...          # re-check for reminders
```

Items carry a `type` (`event|maintenance|campaign|community_event|deadline|publication`), a UTC instant
or an all-day date, a status and an in-portal route. Each source has `calendar.sourceTimeoutMs`; a slow or
failing source only shows its own banner. Deadlines come only from their owners. Built-in sources: `news`
(publications; scheduled ones for editors) and `maintenance` (006, holders of `services.read`).
Reminders are opt-in (`calendar.reminderLeadOptions`), fired once through `notifications.send`; at fire time
the item is fetched again as the user: moved ⇒ the reminder follows (with a notice), removed or no longer
visible ⇒ cancelled.

## Translations

Articles and pages may have per-language translations (`PUT …/translations/{language}`); readers get their
language when it exists, otherwise the source text flagged "not translated".
