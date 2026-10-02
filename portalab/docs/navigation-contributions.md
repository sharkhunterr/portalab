# Navigation contributions (spec 004)

Modules and plugins never touch the menu directly: they **declare** navigation contributions; the backend
assembles, permission-filters and orders them per user (`GET /api/v1/me/navigation`).

```python
from portalab.capabilities.navigation import register_contribution

register_contribution({
    "key": "media.library",            # namespaced: "<module>." or "plugin.<key>."
    "owner": "module:media",           # or "plugin:<key>"
    "kind": "entry",                   # entry | command | related_link | crumb_parent
    "label_key": "nav.media",          # i18n key (026)
    "icon": "film",
    "route": "/media",
    "group": "main",
    "order_hint": 30,
    "required_permission": "media.read",   # mandatory: the API it leads to stays the real boundary
    "visible_when": {"module": "media"},   # optional: module/plugin enablement, boolean setting
})
```

* **Closed schema**: unknown fields, a missing permission, a key outside the owner's namespace or an external
  route are rejected; duplicates keep the first registration. Rejections are recorded
  (`shell.contribution_errors`, `GET /api/v1/admin/shell/contribution-errors`) and announced once
  (`navigation.contribution_rejected`); the rest of the navigation is unaffected.
* **Commands** (palette) may carry `action_id`, `keywords`, `sensitivity` and `confirmation_required`.
  `related_link` / `crumb_parent` attach to an existing entry through `target_entry_key`.
* **Filtering**: an entry is present only if its owner (and `visible_when`) is enabled and the principal holds
  `required_permission`; hidden entries are absent from the response (no names leak). An authorization failure
  serves an empty, `degraded` navigation — never more rights.
* **Ordering**: admin layout (`shell.navigation.layout`: `order`, `pinned`, `groups_of`, `group_order`;
  `PUT /api/v1/admin/shell/layout`, `shell.manage`) > user order (`shell.navigation.userOrder`, when
  `shell.navigation.allowUserOrdering`) > `order_hint`; ties `(order_hint, modules before plugins, key)`.
* **Freshness**: rights/enablement/layout changes bump epochs (`shell.epochs`) and publish
  `navigation.changed` on the live stream (`GET /api/v1/stream`); clients refetch (ETag/304 supported).
* **Withdrawal**: `default_navigation.unregister("plugin:<key>")` removes every contribution of an owner.

Frontend: routes are lazy-loaded under the persistent shell (`frontend/src/shell/router/routes.tsx`); route
handles declare `crumb`, `existenceSensitive` and `requiredPermission` (UI hint).
