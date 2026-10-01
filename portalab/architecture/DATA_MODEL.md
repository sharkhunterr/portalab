# Functional Data Model

Conceptual entities, not a database schema.

Core:
User, Role, Permission, Preference, VisibilityPolicy, Notification, Event, HistoryEntry, AuditEntry.

Services:
Service, Connector, Capability, SyncJob, Incident, Maintenance.

Content/support:
MediaObject, NewsArticle, CalendarEvent, Ticket, WikiPage, Feedback.

Gamification:
Statistic, Achievement, Quest, Level, RewardRule, EconomyTransaction.

Marketplace/community:
MarketplaceProduct, Purchase, CommunityProject, Vote, Funding.

Extensions:
Plugin, Module, Theme, Automation, AutomationExecution.

Important relations:
User → roles/preferences/progression/activity/transactions/purchases/votes/funding.
Service → connector/capabilities/sync/incidents/maintenance.
Media → external identities/sessions/statistics/achievements/events.
Product → purchases/unlocks.
Project → votes/funding/lifecycle.
Plugin → permissions/capabilities/pages/widgets/events/configuration.
