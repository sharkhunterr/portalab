# Statistics (spec 017)

Statistics are **declared by the Admin** (and shipped by domain modules as packs) — users choose, filter,
change the period and hide hideable sections, but never author charts or queries.

## Definitions (closed set)

A `StatisticDefinition` (`portalab.capabilities.statistics`) is validated data, versioned (append-only):

| Field | Meaning |
| --- | --- |
| `key`, `title_key`, `description_key`, `domain` | identity and catalog labels (`statistics:` namespace) |
| `scope` | `personal` (one user's own values), `community` / `global` (aggregates) |
| `event_types` | registered 007 event types folded into the statistic |
| `filter` | clauses `{field, op, value}` with `op` in `eq ne in gt gte lt lte` |
| `measure` | `count`, `sum`, `avg`, `min`, `max`, `distinct_count` (+ `field`) |
| `dimensions` | up to two breakdown fields |
| `viz` | `line`, `bar`, `area`, `pie`, `number`, `table` |
| `hideable`, `required_permission` | consumption controls |
| `min_cohort_size` | privacy threshold for aggregates (never below `statistics.defaultMinCohortSize`, 5) |
| `unlock` | condition tree: `level_at_least`, `achievement_earned`, `product_owned`, `campaign_active`, `all_of`, `any_of` |
| `sources` | service ids whose health makes the value `partial` / `unavailable` |

Fields used in filters, dimensions and measures must be **envelope fields** (`actor`, `subject`, `source`)
or declared `aggregatable` by every listed event type (`EventType(aggregatable=…)`). There is no
expression language.

## Computation

Each active version is a 007 consumer that folds events into daily buckets in **one statistics time
zone** (`statistics.timezone`, default the portal zone) — days are computed when the event is folded, weeks,
months and years are rolled up when read (`statistics.firstDayOfWeek`). A new version starts at the
beginning of the event log (activation computes history). Change policies:

- `forward_only` (default): earlier days keep the values computed under the earlier version, the new rule
  applies from activation on;
- `rebuild`: everything is recomputed under the new version (admin rebuild, confirmed).

Folding is idempotent inside the bucket transaction (`stats.applied_events`), so redelivery and 007
replays never double count.

## Reading: the provider

`StatisticsProvider.get(key, viewer=, subject=, period=, filters=)` (capability `statistics.provider`) is
the only read path — the API, the `statistics.card` dashboard widget, Wrapped, gamification and AI tools all
get the same values. It enforces, in order: permission, unlock (locked ⇒ hint only, nothing computed),
privacy (another user's personal statistic needs their visibility; aggregates below the cohort threshold
are `insufficient_data`, small breakdown cells are merged into "other" so totals never reveal them), a
bounded number of buckets (`statistics.maxBucketsPerRequest`), trends against the previous equal period and
source states (`partial`, `stale` with `as_of`, `unavailable`).

## Packs

`register_definition_pack(domain, definitions, owner=…)` — built-in packs live in
`backend/definitions/packs/*.json` and are activated the first time they are installed; plugin packs
(`plugin_<key>.` keys) install **inactive** until the Admin enables them.

## Wrapped

`/admin/statistics/wrapped` defines recaps (ordered statistic keys over a month, quarter or year). A daily
job generates immutable snapshots for the last completed period — per user (computed as that user, so
permissions and unlocks hold; erased with the account) and for the community (thresholds apply).

## Settings

`statistics.timezone`, `statistics.firstDayOfWeek`, `statistics.defaultMinCohortSize` (5),
`statistics.staleAfterSeconds` (900), `statistics.maxBucketsPerRequest` (800),
`statistics.bucketRetentionMonths` (36), `statistics.wrapped.enabled`; user `statistics.hiddenSections`.
