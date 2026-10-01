# Product Blueprint — Personal Extensible Portal

## Vision
An extensible personal portal that becomes the primary entry point to a digital environment. It centralizes services while providing interaction, discovery, support, community participation, progression, Marketplace, AI and supervision.

It is an experience layer above services, not a simple dashboard, Plex frontend, monitoring-only app, social network, CMS or standalone Marketplace.

## Architecture
PORTAL → Core / Modules / Plugins / Connectors / Services / Capabilities

Cross-cutting systems:
AI, Search, Events, History, Synchronization, Automation, Gamification, Statistics, Notifications, Privacy, Observability.

## Core principles
- Modules depend on capabilities, not concrete services.
- Events decouple features.
- Historized does not mean public.
- AI never has more rights than the current user.
- Permissions are server-side.
- Themes change presentation, not functional truth.
- External services remain sources of truth for native data.
- Partial failures must not break unrelated functions.
- The system must evolve without rewriting the core.

## Modules
Home, Media, Community, Statistics, Support, Marketplace, Services, News, Calendar, Administration.

## Plugins
Optional portal functionality. A plugin can add pages, features, widgets, statistics, permissions, configuration, events, or enrich existing detail pages. Marketplace plugins activate immediately after purchase unless explicit admin configuration is required.

## Connectors / Services / Capabilities
Connector = external integration.
Service = concrete instance.
Capability = functional ability exposed to the portal.

## Home
Widgets include current activity, events, news, requested media, progression, service status, community projects, Since Last Login and Marketplace widgets. Widgets load independently.

## Community
Members, Activity, Leaderboards, Quests, Achievements, Community Projects, Proposals, Funding, Profile. No core friends/followers/DM/chat system.

## Gamification
Exactly three tracked values:
- XP = progression
- Contribution = value brought to community
- Coins = internal virtual currency

Levels are progression tiers, not a fourth currency.

## Coins
Strictly virtual/internal. No real-money coin purchases in the current product. Normally non-negative. Fully auditable. Destroyed on final account deletion.

## Events
Campaign/context such as Halloween. Can define dates, recurrence, multipliers, achievements, quests, notifications, themes and email behavior. Multiple events may overlap; conflict resolution is deterministic.

## Automations
WHEN → IF → THEN reactions to events/conditions. Not a full n8n clone.

## Marketplace
Core convergence point. Products may be plugins, widgets, statistics, themes, effects, badges/titles, quotas, features or community projects. Request quotas can be purchased but paid processing priority does not exist.

## Community projects
Everyone with an active account can vote. Voting is free and independent from coin funding. Funding does not guarantee implementation. Reserved funds are refunded or consumed according to published project rules.

## Support
Tickets, incidents, Wiki, feedback and contextual help. Ticket = individual issue. Incident = broad/systemic issue. AI may diagnose and prefill a ticket; user reviews before submission.

## AI
Can understand, search, explain, recommend, navigate and act. Uses current user permissions. Sensitive actions require confirmation where appropriate. Search and AI run in parallel.

## Search
Classic search results appear immediately while AI analyzes in parallel. Failure of one does not block the other.

## Notifications
Notification, alert, news and email are distinct. Channels include portal, email, sound and future push. User controls categories where policy allows.

## Privacy
Visibility can be Public, Community, Leaderboard only or Private. User preference and admin policy are separate. An admin can temporarily force visibility/private status while preserving the user's preference; removing the policy restores the preference.

## Dashboard
Users can add/remove/reorder/resize/configure widgets within policy. Admin policies can make widgets free, default, mandatory, locked, disabled or conditional. Starter dashboard is automatically configured during onboarding.

## Services / supervision
Service details can expose state, uptime, errors, incidents, maintenance, sync, CPU, RAM, disk, temperature, network, GPU, transcoding/load and server operations according to permissions.

## Data
External services remain sources of truth. Portal stores the representation/history it needs. Disconnecting a service removes live access/sync but does not automatically erase portal history.

## Administration
Exactly one Admin account. Domains include users, modules/plugins, connectors/services, content, support, gamification, Marketplace, statistics, notifications, AI, appearance, security, audit, automations and portal health.

## Product loop
User/service action → Event → History → Statistics/Gamification/Community → AI/Achievements/Marketplace/Projects → Notifications → User → new action.

## Final definition
A personal extensible portal that makes an entire digital environment visible, understandable, usable, interactive and continuously evolutive.
