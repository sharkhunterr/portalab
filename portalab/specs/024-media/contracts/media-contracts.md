# Contracts — Media

## Capabilities (declared in `capabilities/media`; implemented by connectors)
- `media.library` (**sync only**): connector emits `SourceRecord(kind=<MediaType>, external_id, payload{title, ids{scheme:value}, parent_ref?, metadata…, available: bool}, removed)`; Media `RecordSink` upserts.
- `media.playback` (**live**): `now_playing(service) -> list[SourcePlayback]`, `recent_history(service, since) -> Iterable[SourceHistoryItem]`; results typed with `as_of`.
- `request.service` (**live + sync**): `submit(service, media_ref, requester_link) -> SourceRequest`, `status(service, external_request_id)`; sync emits request records.
- Conformance kits for each capability (001 rule) + fake providers for tests.

## Media capability for other modules (`capabilities/media_core`)
`MediaCatalog.get(object_id, viewer) / resolve_ref(ref)`; `MediaHistoryReader.for_user(user, filters)` (privacy-bounded); `ProgressReader`; `RequestQuotaService` (owned by Media, OQ-72): `base_quota(user, period)`, `available(user)`, `add_units(user, units, source_ref, idempotency_key)` / `remove_units(...)` (called by 015 on quota purchase/refund), `consume(user, request_ref)` — never consulted for ordering or priority; `RecommendationProvider.recommend(viewer, ctx) -> list[MediaRef]`; `MediaType` registry (`register_media_type(kind, label_key, parent_kinds, finished_threshold, detail_slots)`); detail slot registry `register_detail_block(slot, block_def)` (declarative template + permission).

## HTTP (`/api/v1`)
| Path | Permission | Notes |
|---|---|---|
| GET `/media?kind&genre&year&availability&q&cursor` | `media.read` (default grant) | catalog; visibility/privacy bounded |
| GET `/media/{id}` | `media.read` | core info + section manifest |
| GET `/media/{id}/sections/{info|sources|history|progress|requests|people|statistics|events|actions|links|blocks}` | `media.read` (+ visibility for personal sections) | each section returns `{state, as_of, data}` independently |
| GET `/media/images/{id}` | `media.read` | proxy from blobstore |
| GET `/me/media/now-playing`, `/me/media/continue`, `/me/media/history?cursor` | self | |
| GET `/media/discovery/{shelf}` | `media.read` | `new|recent|continue|trending|recommended` |
| POST `/media/requests` · GET `/me/media/requests` · POST `/media/requests/{id}/cancel` | `media.request` (default grant) | quota check; idempotency key |
| GET/POST `/me/media/links` (+ verify) · DELETE `/me/media/links/{id}` | self | user↔service identity mapping |
| GET `/admin/media/match-candidates` · POST `…/{id}/accept|reject` · POST `/admin/media/merge` · `/admin/media/split` | `media.manage` (sensitive, audited, confirmation) | reversible |
| PUT `/admin/media/objects/{id}/overrides` | `media.manage` (audited) | per-field admin override |
| GET `/admin/media/unlinked-activity` | `media.manage` | unattributed source activity (no content bodies) |
Problem codes: `media.not_found`, `media.request_quota_exceeded`, `media.service_unavailable`, `media.link_unverified`, `media.merge_conflict`.

## Integrations provided
`SearchProvider(kind="media")` + `ObjectResolver` (008) · widgets `media.continue|recent|now_playing|requests` (009) · statistics packs `media`, `playback`, `reading`, `gaming` (017) · notification categories `media.available`, `media.request_updated`, `media.new_in_library` (010) · AI read tools (018, principal-bounded) · palette actions `media.request`, `media.open` (004/008).

## Frontend
`/media` home (shelves), catalog browse (grid/list, filters), detail page of independent section frames + plugin block slots, now-playing/continue components, request flow, link-account settings, admin matching/merge screen.
