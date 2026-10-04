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

## Sections (spec 027)

The menu is organized in **sections**, not a flat list. `group` names the section of an entry and `topic`
an optional sub-group (used by Administration):

```python
from portalab.capabilities.navigation import register_section

register_section({
    "key": "games",                    # plugins: "plugin-<key>" or "plugin-<key>-<name>"
    "owner": "module:games",
    "label_key": "nav.section.games",
    "icon": "game",                    # design-system icon name
    "order_hint": 45,
    "audience": "everyone",            # everyone | administration | personal (avatar menu)
    "topics": (),                      # optional sub-groups: ({"key", "label_key", "order_hint"}, …)
    "default_for": ("module:games",),  # owners whose unplaced entries land here
})
```

Built-in sections: `home`, `media`, `content` (Discover), `services`, `community`, `marketplace`, `support`,
`more` (fallback), `me` (personal pages, shown in the avatar menu) and `admin` (topics `access`, `services`,
`content`, `economy`, `system`, `extensions`). An entry naming an unknown section lands in its owner's default
section, else in `more` — never dropped — and a `navigation.section_unknown` diagnostic is recorded (the 004
default `main` is routed silently). Sections without a usable entry are absent; a section with one entry and
no topic renders as a direct link. `GET /api/v1/me/navigation` returns `sections`, `personal` and, for one
release, the 004 `groups` shape. Plugins declare `[[ui.sections]]` and `section = "plugin-<key>"` on their
`ui.nav` entries (`ctx.nav_section()` / `ctx.nav_entry(..., group=, topic=)` from code). Administrators can
re-assign entries (`groups_of`), order sections (`group_order`) and rename them (`section_labels`).

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
