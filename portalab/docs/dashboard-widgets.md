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
