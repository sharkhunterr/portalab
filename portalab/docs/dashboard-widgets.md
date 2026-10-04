# Dashboard widgets (spec 009)

The dashboard module owns **composition only**: which widgets a user has, where, at what size, under
which administrator policy. Every widget's data comes from its owning module through a provider, loads on
its own and reports a standard functional state — one widget's outage never affects another.

## Registering a widget (`portalab.capabilities.dashboard`)

```python
from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload, default_widgets

WIDGET = WidgetDefinition(
    key="wiki.recent",                     # plugins: "plugin:<key>.<name>"
    owner="module:wiki",
    title_key="wiki:widget.recent.title",  # catalog key (namespace:key)
    required_permission="wiki.read",
    config_schema={"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
                   "additionalProperties": False},
    config_defaults={"limit": 5},
    size=SizeLimits(default=Size(4, 2), min=Size(3, 2), max=Size(12, 6)),
    refresh=Refresh(mode="event", events=("wiki.page_published",)),  # → SSE widget.invalidate
    stale_after_s=900,
    template="list",                       # or component_id for a first-party component
)

class RecentPages:
    async def load(self, principal, config, ctx) -> WidgetPayload:
        # authorize + apply visibility here; raise WidgetUnavailable / WidgetUnauthorized when needed
        return WidgetPayload("available", as_of=now, data={"items": [...]})

default_widgets.register(WIDGET, RecentPages(), owner="module:wiki")
```

- `WidgetPayload.state`: `available | partial | stale | unavailable | error | unauthorized | no-data`;
  `stale` is computed from `as_of` + `stale_after_s`; timeouts (`dashboard.widgetTimeoutMs`, 5 s) and
  exceptions become `unavailable` / `error` — never a 5xx.
- The gateway re-checks on every call: the widget permission, the owner module/plugin being enabled and,
  for Marketplace widget products (`product=`), the user's entitlement (015).
- Configuration is validated with the JSON Schema; an invalid stored configuration falls back to the
  defaults and the payload says `config_invalid`.

## Templates (declarative widgets)

Plugins and Marketplace widgets are declarative — data plus one of `stat`, `list`, `chart`, `timeline`,
`status`; they never ship code to the SPA. `register_plugin_widget(registry, plugin_id, manifest,
provider)` namespaces the key, hardens string settings (no markup, bounded length) and the widget is
withdrawn on `plugin.state_changed` (users keep a placeholder and their settings until reactivation).

| Template | `data` shape |
| --- | --- |
| `stat` | `{value, label?, unit?, trend?}` |
| `list` | `{items: [{title, route?, meta?}]}` |
| `chart` | `{series: [{label, points: [[x, y]]}]}` |
| `timeline` | `{entries: [{at, title, route?}]}` |
| `status` | `{counts: {state: n}, items: [{name, state, route?}]}` |

## Policies (Administration, `dashboard.widgetPolicies`)

`{widget_key: {class, condition?, lockedConfig?}}` — evaluated **on read**, never written into users'
rows, so relaxing a policy restores each user's previous choices.

| Class | Effect |
| --- | --- |
| `free` | the user decides |
| `default` | offered with the starter dashboard, then the user decides |
| `mandatory` | shown to everyone (permission permitting); cannot be hidden or removed |
| `locked` | cannot be moved, resized or reconfigured (`lockedConfig` forced) |
| `conditional` | shown only when its condition holds |
| `disabled` | never shown, cannot be added |

Conditions are a closed set: `role_in`, `permission`, `service_state`, `campaign_active`,
`module_enabled`, `data_present` (`{"type": "...", "value": ...}`); an unknown condition hides the widget
with a diagnostic. `dashboard.starterLayout` lists `{widget_key, w, h, roles?}` applied once per user.
Admin API: `GET/PUT /api/v1/admin/dashboard/policies|starter` (`dashboard.manage`, audited).

## "Since last login"

Register a `ChangeSummaryProvider` (`kind`, `changes_since(principal, since, limit, ctx)`) with
`default_widgets.register_summary(provider, owner=...)`: apply permissions and privacy at the source;
`tests/contract/dashboard/provider_kit.py` checks the contract. The boundary only moves when the user
marks the summary as seen.

## 2D arrangement and the editor (spec 027)

Each widget instance has grid coordinates `x` (column 0–11) and `y` (row) besides its size `w`×`h` (cells,
bounded by the widget's `SizeLimits`). The arrangement engine — `frontend/src/features/dashboard/grid/
engine.ts` and its server twin `backend/src/portalab/modules/dashboard/arrangement.py`, held together by the
shared cases in `tests/fixtures/dashboard-arrangements.json` — keeps widgets from overlapping, makes them float
up into free space, pushes widgets out of the way of a moved/resized one, and never moves a locked widget.
`position` is the derived reading order (row, then column): it is the DOM order and the order of the tablet
(6 columns) and phone (2 columns) views, which are computed from the desktop arrangement and never stored.

- `GET /api/v1/dashboard` returns `x`, `y`, `w`, `h` and `position` per instance;
- `PUT /api/v1/dashboard/arrangement` (If-Match) stores the editor's arrangement in one write — coordinates
  are bounded, overlaps resolved, omitted widgets kept; locked widgets refuse changes (`dashboard.policy_locked`);
- `POST /api/v1/dashboard/widgets` places a new widget at the first free slot, or where it was dropped (`x`, `y`);
- `PATCH /api/v1/dashboard/widgets/{id}` accepts `x`, `y` (move) and `w`, `h` (resize); neighbours make room;
- `PUT /api/v1/dashboard/layout` (ordered list) is deprecated: the order is flowed into rows.

Editor: on desktop, *Customize* starts a session — drag a widget by its grip, resize it by its corner, or use
the keyboard (focus the grip, Enter, arrow keys to move, Shift + arrows to resize, Enter to drop) or the
explicit buttons; *Save* sends the arrangement, *Cancel* drops the draft. Tablets and phones offer add, hide,
remove and reorder. The gallery shows every widget the user may add with its icon, description and sizes.
Existing ordered dashboards were flowed into the grid by the `dashboard_0002` migration.
