# Extensibility Model

## Extension types
- Module = major portal area.
- Plugin = optional portal functionality.
- Connector = external integration.
- Service = concrete service instance.
- Capability = functional ability.
- Widget = reusable UI unit.
- Theme = presentation layer.
- Automation = event/condition reaction.

## Plugin can
- add page;
- add feature;
- add widget;
- enrich detail page;
- add statistics;
- add permissions;
- add settings;
- consume/produce events;
- add relations.

## Lifecycle
Available → Installed → Configured → Enabled → Updated → Disabled → Archived/Removed

Marketplace:
Purchased → Unlocked → Enabled immediately by default.

## Isolation
Disabling a plugin does not delete its data. A plugin failure must not break unrelated functions.

## Compatibility
Check portal version, dependencies, capabilities, permissions and configuration before activation/update.

## Evolution
Prefer existing capabilities, events, history, permissions, configuration and design system over isolated parallel mechanisms.
