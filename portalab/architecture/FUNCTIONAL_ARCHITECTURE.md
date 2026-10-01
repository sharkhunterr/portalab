# Functional Architecture

## Hierarchy
PORTAL
├── Core
├── Modules
├── Plugins
├── Connectors
├── Services
└── Capabilities

## Core
Identity, users, permissions, navigation, search, Command Palette, notifications, configuration, events, history, privacy, audit, theme, accessibility, extensions, synchronization, observability.

## Modules
Home, Media, Community, Statistics, Support, Marketplace, Services, News, Calendar, Administration.

## Plugin
Optional portal feature/page/extension. Can enrich modules or detail pages.

## Connector
External integration.

## Service
Concrete connected instance.

## Capability
Functional contract between service integrations and portal modules.

## Key principle
Modules depend on capabilities, not service names.

## Cross-cutting loop
Source/user action → Event → History → interested consumers → Notification/action → User.
