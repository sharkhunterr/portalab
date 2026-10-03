# Media (spec 024)

Media is the portal's **service-independent catalog**: one Media Object per work, whatever services list it,
with per-field provenance, normalized playback, a history fed by events, requests within a quota and an
extensible detail page. It contains no provider-specific code: Plex, Jellyfin, Sonarr, Seerr, RomM… are
connectors (spec 005) that implement the capabilities below.

## Capabilities a connector implements (`portalab.capabilities.media`)

| Capability | Kind | What the connector provides |
| --- | --- | --- |
| `media.library` | sync | `SourceRecord(kind=<media type>, external_id, payload=LibraryPayload)` from `sync`; per-service provider with `fetch_image(ref)` |
| `media.playback` | live | `now_playing()` → `SourcePlayback[]`, `recent_history(since)` → `SourceHistoryItem[]`; optional `verify_user(account, code)` |
| `request.service` | live + sync | `submit(ids, kind, title, requester)` / `status(id)` (optional `cancel(id)`); sync records with `RequestPayload` |

`LibraryPayload`: `title`, `ids` (`tmdb`, `imdb`, `tvdb`, `isbn`, `igdb`, `musicbrainz`…), `parent` (external id
of the parent item) + `position`, `year`, `overview`, `genres`, `people`, `language`, `duration_s`, `pages`,
`image` (an opaque ref), `available`. Unknown fields are dropped; image URLs lose credentials and query strings.

Prove a connector with the kits in `portalab.capabilities.media.testkit` (`LibraryRecordKit`,
`PlaybackContractKit`, `RequestServiceContractKit`) and the 005 `RecordSinkContractKit`.

## Identity and matching

- **id-first**: a record sharing a strong id with an object resolves to it; children without ids resolve by
  `(parent, kind, position)`; ids already owned by another object are never moved (no silent merge).
- Similar titles of the same kind and year without conflicting ids become **match candidates**
  (`media.match.autoThreshold`, default 0.85) that an administrator merges or rejects.
- Merge/split (`media.manage`, confirmation + audit) are logged in the append-only `media.merge_log` and
  reversible: a split restores exactly the rows the merge moved. Objects are never deleted by a sync.

## Field priority

Every source's value is kept (`media.field_candidates`). The effective value follows
`media.fieldPriority.<kind>.<field>` — an ordered list of connector keys (`plex`) or one service
(`plex:<service id>`) — then active sources before inactive ones, then name order. An administrator
override (`PUT /admin/media/objects/{id}/overrides`) beats every source; the winner of each field is kept as
provenance.

## Availability, service health, sync state

The `sources` section returns the three facts side by side: the object's availability (an active source lists
it as available), each service's health (006) and its last sync outcome (005). An outage or a failed sync
changes none of the catalog facts.

## Playback and history semantics

- Sessions are polled (15 s while something plays, 60 s idle), normalized and stored; events:
  `media.playback_started|paused|progressed|finished|abandoned|error` (progress at most every
  `media.playback.progressEventSeconds`), dedup `(session, state_seq)`, `finished` once per session.
- A session ends `finished` when the furthest position reached the kind's threshold
  (`media.finishedThreshold.<kind>`: movie/episode 90 %, book 95 %, track 80 %; games: explicit only),
  else `abandoned`. A source that stops answering makes sessions `stale`, then `interrupted` with
  `media.playback_error` after `staleTimeoutSeconds` — never `finished`.
- Only **verified** account links attribute activity; everything else stays unlinked (admin sees counts only).
- The event stream is the record: `media.history_entries` / `media.user_progress` are a projection keyed by
  event id (replays are no-ops). The resume point follows the latest `occurred_at` across sources;
  `finished` is sticky. Personal history is the `media_history` datum class (private by default).

## Requests and quota

`POST /media/requests` checks the quota (base `media.requests.quotaPerPeriod` per `media.requests.period`,
then extra units), submits to the request service and mirrors its state; sync records from the service are
the source of truth. Extra units are credited by Marketplace (015) through `media.request_quota`
(`add_units` / `remove_units`, idempotent and ledgered). Units only allow *more* requests — order and
priority never depend on them. A failed submission gives the quota back.

## Integrations

Search provider `media` (+ resolver `media:`/`tmdb:`… and palette actions), widgets `media.continue`,
`media.recent`, `media.now_playing`, `media.requests`, statistics packs `media`, `playback`, `reading`,
`gaming`, notification categories `media.available`, `media.request_updated`, `media.new_in_library`,
`activity.attributes` for media events (014/019), AI read tools (018) and `media.catalog` /
`media.history` ports. See [media-extensibility.md](media-extensibility.md).

## API

`GET /media`, `GET /media/{id}`, `GET /media/{id}/sections/{name}`, `GET /media/images/{id}`,
`GET /media/discovery/{shelf}`, `POST /media/requests`, `POST /media/requests/{id}/cancel`,
`GET /me/media/now-playing|history|continue|requests|links`, `POST /me/media/links` (+ `/verify`),
`DELETE /me/media/links/{id}`; admin: `GET /admin/media/match-candidates`, `POST …/{id}/reject`,
`POST /admin/media/merge|split`, `PUT /admin/media/objects/{id}/overrides`,
`GET /admin/media/unlinked-activity|status`, `POST /admin/media/links/{id}/verify`.
