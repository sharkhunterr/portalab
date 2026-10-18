import { lazy } from "react";
import { createBrowserRouter, Navigate, type RouteObject } from "react-router";
import type { RouteHandle } from "./handle";
import { RouteErrorElement } from "./RouteBoundary";

/**
 * Route table (spec 004 T002/T019): every page is lazy-loaded (one chunk per area) inside the persistent
 * shell. Handles carry breadcrumb labels and existence sensitivity; permissions stay a UI hint (the API
 * decides). Unknown paths render "not available".
 */
const Home = lazy(() => import("../../features/dashboard/DashboardPage"));
const Account = lazy(() => import("../../pages/AccountRoute"));
const Guide = lazy(() => import("../../features/onboarding/GuidePage"));
const Appearance = lazy(() => import("../../pages/AppearanceRoute"));
const Privacy = lazy(() => import("../../pages/PrivacyRoute"));
const Services = lazy(() => import("../../pages/ServicesRoute"));
const ServiceDetail = lazy(() => import("../../pages/ServiceDetailRoute"));
const ControlCenter = lazy(() => import("../../pages/admin/ControlCenterRoute"));
const Configuration = lazy(() => import("../../pages/admin/ConfigurationRoute"));
const ServicesAdmin = lazy(() => import("../../pages/admin/ServicesAdminRoute"));
const Roles = lazy(() => import("../../pages/admin/RolesRoute"));
const PrivacyAdmin = lazy(() => import("../../pages/admin/PrivacyAdminRoute"));
const TermsAdmin = lazy(() => import("../../features/terms/TermsAdmin"));
const Audit = lazy(() => import("../../pages/admin/AuditRoute"));
const Events = lazy(() => import("../../pages/admin/EventsRoute"));
const Observability = lazy(() => import("../../pages/admin/ObservabilityRoute"));
const Incidents = lazy(() => import("../../features/support/incidents/IncidentsPage"));
const IncidentConsole = lazy(() => import("../../features/support/incidents/IncidentConsole"));
const Statistics = lazy(() => import("../../features/statistics/StatisticsPage"));
const Wrapped = lazy(() => import("../../features/statistics/wrapped/WrappedStory"));
const StatisticsAdmin = lazy(() => import("../../features/statistics/admin/DefinitionsAdmin"));
const Notifications = lazy(() => import("../../features/notifications/bell/OpenNotifications")); // issue 112
const NotificationSettings = lazy(
  () => import("../../features/notifications/preferences/NotificationPreferences"),
);
const MediaHome = lazy(() => import("../../features/media/home/MediaHome"));
const MediaCatalog = lazy(() => import("../../features/media/catalog/CatalogPage"));
const MediaDetail = lazy(() => import("../../features/media/detail/DetailPage"));
const MediaPlayer = lazy(() => import("../../features/media/player/PlayerPage"));
const MediaReader = lazy(() => import("../../features/media/reader/ReaderPage"));
const MediaRequests = lazy(() => import("../../features/media/requests/RequestsPage"));
const MediaDiscover = lazy(() => import("../../features/media/discover/DiscoverPage"));
const MediaDiscoverTitle = lazy(() => import("../../features/media/discover/DiscoverTitlePage"));
const MediaPerson = lazy(() => import("../../features/media/people/PersonPage"));
const MediaInsights = lazy(() => import("../../features/media/insights/InsightsPage"));
const MediaAccounts = lazy(() => import("../../features/media/links/LinksSettings"));
const MediaAdmin = lazy(() => import("../../features/media/admin/MatchingScreen"));
const MediaSourcesAdmin = lazy(() => import("../../features/admin/media/MediaSourcesAdmin"));
const MediaQuotasAdmin = lazy(() => import("../../features/admin/media/RequestQuotasAdmin"));
const MediaRequestsAdmin = lazy(() => import("../../features/admin/media/RequestsAdmin"));
const NewsPage = lazy(() => import("../../features/news/NewsPage"));
const Article = lazy(() => import("../../features/news/ArticlePage"));
const NewsAdmin = lazy(() => import("../../features/news/NewsAdmin"));
const WikiHome = lazy(() => import("../../features/wiki/WikiHome"));
const WikiPage = lazy(() => import("../../features/wiki/PageView"));
const WikiEditor = lazy(() => import("../../features/wiki/PageEditor"));
const WikiHistory = lazy(() => import("../../features/wiki/History"));
const CalendarPage = lazy(() => import("../../features/calendar/CalendarPage"));
const MyTickets = lazy(() => import("../../features/support/tickets/MyTickets"));
const NewTicket = lazy(() => import("../../features/support/tickets/NewTicket"));
const TicketPage = lazy(() => import("../../features/support/tickets/TicketPage"));
const SupportQueue = lazy(() => import("../../features/support/staff/Queue"));
const FeedbackReview = lazy(() => import("../../features/support/feedback/ReviewQueue"));
const FeedbackPage = lazy(() => import("../../features/support/feedback/FeedbackPage"));
const DashboardAdmin = lazy(() => import("../../features/dashboard/admin/DashboardAdmin"));
const SupportDefinitions = lazy(() => import("../../features/support/admin/Definitions"));
const AiAdmin = lazy(() => import("../../features/ai/admin/AiAdminPage"));
const Automations = lazy(() => import("../../features/automations/AutomationsPage"));
const CampaignConsole = lazy(() => import("../../features/campaigns/console/CampaignConsole"));
const Campaigns = lazy(() => import("../../features/campaigns/CampaignsPage"));
const GamificationAdmin = lazy(() => import("../../features/gamification/admin/GamificationAdmin"));
const Progression = lazy(() => import("../../features/gamification/progression/ProgressionPage"));
const Community = lazy(() => import("../../features/community/CommunityPage"));
const ModerationQueue = lazy(() => import("../../features/community/projects/ModerationQueue"));
const Projects = lazy(() => import("../../features/marketplace/projects/ProjectsPage"));
const Project = lazy(() => import("../../features/marketplace/projects/ProjectRoute"));
const ProjectConsole = lazy(() => import("../../features/marketplace/admin/ProjectConsole"));
const Catalog = lazy(() => import("../../features/marketplace/catalog/CatalogPage"));
const ProductRoute = lazy(() => import("../../features/marketplace/product/ProductRoute"));
const Owned = lazy(() => import("../../features/marketplace/owned/OwnedPage"));
const Reserve = lazy(() => import("../../features/marketplace/reserve/ReservePage"));
const MarketplaceAdmin = lazy(() => import("../../features/marketplace/admin/MarketplaceAdmin"));
const ThemeStudio = lazy(() => import("../../features/appearance/studio/ThemeStudio"));
const ChartGallery = lazy(() => import("../../features/appearance/charts/ChartGallery")); // issue 117
const MembersAdmin = lazy(() => import("../../features/admin/members/MembersAdmin"));
const AnnouncementsAdmin = lazy(() => import("../../features/admin/communication/AnnouncementsAdmin"));
const WikiAdmin = lazy(() => import("../../features/wiki/WikiAdmin"));
const PluginsAdmin = lazy(() => import("../../features/plugins/manager/PluginsAdmin"));
const VisualsAdmin = lazy(() => import("../../features/visuals/VisualsAdmin")); // 028
const VersionWorkflow = lazy(() => import("../../features/visuals/VersionWorkflow")); // 028
const WidgetPacksAdmin = lazy(() => import("../../features/visuals/WidgetPacksAdmin")); // 028
const SecurityBlocks = lazy(() => import("../../features/security/SecurityBlocks")); // issue 1 (POC)
const ModulesAdmin = lazy(() => import("../../features/plugins/manager/ModulesAdmin"));
const PluginPage = lazy(() => import("../../features/plugins/pages/PageRenderer"));
const Search = lazy(() => import("../../features/search/SearchPage"));
const Language = lazy(() => import("../../features/settings/LanguageSettings"));
const NotAvailable = lazy(() => import("../../pages/NotAvailablePage"));

const h = (handle: RouteHandle) => handle;

export function routes(shell: RouteObject["element"]): RouteObject[] {
  return [
    {
      path: "/",
      element: shell,
      errorElement: <RouteErrorElement />,
      handle: h({ crumb: "Home" }),
      children: [
        { index: true, element: <Home /> },
        {
          path: "incidents",
          handle: h({ crumb: "Incidents", requiredPermission: "incidents.read" }),
          children: [
            { index: true, element: <Incidents /> },
            {
              path: ":incidentId",
              element: <Incidents />,
              handle: h({ crumb: "Incident", existenceSensitive: true }),
            },
          ],
        },
        { path: "progression", element: <Progression />, handle: h({ crumb: "My progression" }) },
        {
          path: "plugins/:pluginKey/:pageKey",
          element: <PluginPage />,
          handle: h({ existenceSensitive: true }), // 030: named by its navigation entry (Breadcrumbs)
        },
        {
          path: "marketplace",
          handle: h({ crumb: "Marketplace", requiredPermission: "marketplace.read" }),
          children: [
            { index: true, element: <Catalog /> },
            { path: "owned", element: <Owned />, handle: h({ crumb: "My products" }) },
            { path: "reserve", element: <Reserve />, handle: h({ crumb: "My reserve" }) },
            {
              path: "products/:key",
              element: <ProductRoute />,
              handle: h({ crumb: "Product", existenceSensitive: true }),
            },
          ],
        },
        {
          path: "projects",
          handle: h({ crumb: "Projects", requiredPermission: "marketplace.read" }),
          children: [
            { index: true, element: <Projects /> },
            {
              path: ":projectId",
              element: <Project />,
              handle: h({ crumb: "Project", existenceSensitive: true }),
            },
          ],
        },
        {
          path: "community",
          handle: h({ crumb: "Community", requiredPermission: "community.read" }),
          children: [
            { index: true, element: <Community view="discover" /> },
            { path: "members", element: <Community view="members" />, handle: h({ crumb: "Members" }) },
            {
              path: "members/:memberId",
              element: <Community view="profile" />,
              handle: h({ crumb: "Member", existenceSensitive: true }),
            },
            { path: "feed", element: <Community view="feed" />, handle: h({ crumb: "Activity" }) },
            {
              path: "leaderboards",
              element: <Community view="leaderboards" />,
              handle: h({ crumb: "Leaderboards" }),
            },
            {
              path: "achievements",
              element: <Community view="achievements" />,
              handle: h({ crumb: "Achievements" }),
            },
            { path: "quests", element: <Community view="quests" />, handle: h({ crumb: "Quests" }) },
            { path: "events", element: <Community view="events" />, handle: h({ crumb: "Events" }) },
            { path: "proposals", element: <Community view="proposals" />, handle: h({ crumb: "Proposals" }) },
            {
              path: "proposals/:proposalId",
              element: <Community view="proposal" />,
              handle: h({ crumb: "Proposal", existenceSensitive: true }),
            },
          ],
        },
        {
          path: "campaigns",
          handle: h({ crumb: "Campaigns", requiredPermission: "campaigns.read" }),
          children: [
            { index: true, element: <Campaigns /> },
            { path: ":key", element: <Campaigns />, handle: h({ crumb: (params) => params.key ?? "" }) },
          ],
        },
        {
          path: "statistics",
          handle: h({ crumb: "Statistics", requiredPermission: "statistics.read" }),
          children: [
            { index: true, element: <Statistics /> },
            { path: "wrapped", element: <Wrapped />, handle: h({ crumb: "Recap" }) },
            {
              path: "wrapped/:snapshotId",
              element: <Wrapped />,
              handle: h({ crumb: "Recap", existenceSensitive: true }),
            },
          ],
        },
        {
          path: "media",
          handle: h({ crumb: "Media", requiredPermission: "media.read" }),
          children: [
            { index: true, element: <MediaHome /> },
            { path: "browse", element: <MediaCatalog />, handle: h({ crumb: "Catalog" }) },
            {
              path: "requests",
              element: <MediaRequests />,
              handle: h({ crumb: "My requests", requiredPermission: "media.request" }),
            },
            { path: "insights", element: <MediaInsights />, handle: h({ crumb: "Statistics" }) },
            {
              // #4: asking for a film or a series — the search and shelves, then a title's page
              path: "discover",
              element: <MediaDiscover />,
              handle: h({ crumb: "Ask for a title", requiredPermission: "media.request" }),
            },
            {
              path: "discover/:kind/:tmdb",
              element: <MediaDiscoverTitle />,
              handle: h({ crumb: "Ask for a title", requiredPermission: "media.request" }),
            },
            {
              // #92: an actor's, a director's, an author's, a narrator's page
              path: "people/:name",
              element: <MediaPerson />,
              handle: h({ crumb: "Person" }),
            },
            {
              path: ":objectId",
              element: <MediaDetail />,
              handle: h({ crumb: "Media", existenceSensitive: true }),
            },
            {
              // 027 (#2): the portal's own player, over the whole window
              path: ":objectId/watch",
              element: <MediaPlayer />,
              handle: h({ crumb: "Watch", requiredPermission: "media.play", existenceSensitive: true }),
            },
            {
              // #21: the book reader, over the whole window (a page of its own, entered by a full load)
              path: ":objectId/read",
              element: <MediaReader />,
              handle: h({ crumb: "Read", requiredPermission: "media.play", existenceSensitive: true }),
            },
          ],
        },
        {
          path: "news",
          handle: h({ crumb: "News", requiredPermission: "news.read" }),
          children: [
            { index: true, element: <NewsPage /> },
            {
              path: ":slug",
              element: <Article />,
              handle: h({ crumb: "Article", existenceSensitive: true }),
            },
          ],
        },
        {
          path: "wiki",
          handle: h({ crumb: "Wiki", requiredPermission: "wiki.read" }),
          children: [
            { index: true, element: <WikiHome /> },
            {
              path: "new",
              element: <WikiEditor />,
              handle: h({ crumb: "New page", requiredPermission: "wiki.edit" }),
            },
            { path: ":slug", element: <WikiPage />, handle: h({ crumb: "Page", existenceSensitive: true }) },
            {
              path: ":slug/edit",
              element: <WikiEditor />,
              handle: h({ crumb: "Edit", existenceSensitive: true }),
            },
            {
              path: ":slug/history",
              element: <WikiHistory />,
              handle: h({ crumb: "History", existenceSensitive: true }),
            },
          ],
        },
        {
          path: "calendar",
          element: <CalendarPage />,
          handle: h({ crumb: "Calendar", requiredPermission: "calendar.read" }),
        },
        {
          path: "support",
          handle: h({ crumb: "Support", requiredPermission: "tickets.create" }),
          children: [
            { index: true, element: <MyTickets /> },
            { path: "new", element: <NewTicket />, handle: h({ crumb: "New ticket" }) },
            {
              path: "tickets/:ticketId",
              element: <TicketPage />,
              handle: h({ crumb: "Ticket", existenceSensitive: true }),
            },
            {
              path: "queue",
              element: <SupportQueue />,
              handle: h({ crumb: "Queue", requiredPermission: "tickets.manage" }),
            },
            {
              path: "feedback",
              element: <FeedbackReview />,
              handle: h({ crumb: "Feedback", requiredPermission: "feedback.read" }),
            },
          ],
        },
        {
          path: "feedback",
          element: <FeedbackPage />,
          handle: h({ crumb: "Feedback", requiredPermission: "feedback.submit" }),
        },
        {
          path: "search",
          element: <Search />,
          handle: h({ crumb: "Search", requiredPermission: "search.use" }),
        },
        { path: "notifications", element: <Notifications />, handle: h({ crumb: "Notifications" }) },
        { path: "account", element: <Account />, handle: h({ crumb: "Account" }) },
        { path: "guide", element: <Guide />, handle: h({ crumb: "Guided tours" }) },
        { path: "settings/appearance", element: <Appearance />, handle: h({ crumb: "Appearance" }) },
        { path: "settings/language", element: <Language />, handle: h({ crumb: "Language & region" }) },
        {
          path: "settings/notifications",
          element: <NotificationSettings />,
          handle: h({ crumb: "Notification preferences" }),
        },
        {
          path: "settings/media-accounts",
          element: <MediaAccounts />,
          handle: h({ crumb: "Media accounts" }),
        },
        { path: "privacy", element: <Privacy />, handle: h({ crumb: "Privacy" }) },
        {
          path: "services",
          handle: h({ crumb: "Services", requiredPermission: "services.read" }),
          children: [
            { index: true, element: <Services /> },
            {
              path: ":serviceId",
              element: <ServiceDetail />,
              handle: h({ crumb: (params) => `Service ${params.serviceId ?? ""}`, existenceSensitive: true }),
            },
          ],
        },
        {
          path: "admin",
          handle: h({ crumb: "Administration" }),
          children: [
            { index: true, element: <ControlCenter /> },
            {
              path: "statistics",
              element: <StatisticsAdmin />,
              handle: h({ crumb: "Statistic definitions" }),
            },
            { path: "support", element: <SupportDefinitions />, handle: h({ crumb: "Support settings" }) },
            { path: "ai", element: <AiAdmin />, handle: h({ crumb: "Assistant settings" }) },
            { path: "gamification", element: <GamificationAdmin />, handle: h({ crumb: "Gamification" }) },
            { path: "campaigns", element: <CampaignConsole />, handle: h({ crumb: "Campaigns" }) },
            { path: "automations", element: <Automations />, handle: h({ crumb: "Automations" }) },
            { path: "projects", element: <ProjectConsole />, handle: h({ crumb: "Projects" }) },
            { path: "marketplace", element: <MarketplaceAdmin />, handle: h({ crumb: "Marketplace" }) },
            // #98: the shop's console, one page each in the Shop hub
            ...["members", "requests", "catalog", "boosters"].map((view) => ({
              path: `marketplace/${view}`,
              element: <MarketplaceAdmin />,
              handle: h({ crumb: "Marketplace" }),
            })),
            { path: "themes", element: <ThemeStudio />, handle: h({ crumb: "Theme studio" }) },
            { path: "charts", element: <ChartGallery />, handle: h({ crumb: "Charts" }) },
            { path: "members", element: <MembersAdmin />, handle: h({ crumb: "Members" }) },
            { path: "announcements", element: <AnnouncementsAdmin />, handle: h({ crumb: "Announcements" }) },
            { path: "terms", element: <TermsAdmin />, handle: h({ crumb: "Terms of use" }) },
            { path: "dashboard", element: <DashboardAdmin />, handle: h({ crumb: "Members' dashboard" }) },
            { path: "maintenance", element: <Navigate to="/admin/announcements?tab=maintenance" replace /> },
            { path: "wiki", element: <WikiAdmin />, handle: h({ crumb: "Wiki" }) },
            { path: "plugins", element: <PluginsAdmin />, handle: h({ crumb: "Plugins" }) },
            { path: "visuals", element: <VisualsAdmin />, handle: h({ crumb: "Visual packs" }) },
            { path: "widgets", element: <WidgetPacksAdmin />, handle: h({ crumb: "Widgets" }) },
            {
              path: "visuals/:pack/:version",
              element: <VersionWorkflow />,
              handle: h({ crumb: "Pack version" }),
            },
            { path: "security-blocks", element: <SecurityBlocks />, handle: h({ crumb: "Security blocks" }) },
            { path: "modules", element: <ModulesAdmin />, handle: h({ crumb: "Modules" }) },
            {
              path: "community/moderation",
              element: <ModerationQueue />,
              handle: h({ crumb: "Moderation" }),
            },
            { path: "automations/new", element: <Automations />, handle: h({ crumb: "New automation" }) },
            { path: "automations/history", element: <Automations />, handle: h({ crumb: "Run history" }) },
            { path: "automations/templates", element: <Automations />, handle: h({ crumb: "Templates" }) },
            { path: "automations/approvals", element: <Automations />, handle: h({ crumb: "Approvals" }) },
            { path: "automations/:id", element: <Automations />, handle: h({ crumb: "Automation" }) },
            { path: "automations/:id/edit", element: <Automations />, handle: h({ crumb: "Edit" }) },
            { path: "news", element: <NewsAdmin />, handle: h({ crumb: "News desk" }) },
            { path: "media", element: <MediaAdmin />, handle: h({ crumb: "Media identity" }) },
            { path: "media-quotas", element: <MediaQuotasAdmin />, handle: h({ crumb: "Request quotas" }) },
            { path: "media-requests", element: <MediaRequestsAdmin />, handle: h({ crumb: "Requests" }) },
            {
              path: "media-sources",
              element: <MediaSourcesAdmin />,
              handle: h({ crumb: "History and metadata" }),
            },
            { path: "incidents", element: <IncidentConsole />, handle: h({ crumb: "Incident console" }) },
            { path: "configuration", element: <Configuration />, handle: h({ crumb: "Configuration" }) },
            { path: "services", element: <ServicesAdmin />, handle: h({ crumb: "Services" }) },
            { path: "roles", element: <Roles />, handle: h({ crumb: "Roles & permissions" }) },
            { path: "privacy", element: <PrivacyAdmin />, handle: h({ crumb: "Privacy policies" }) },
            { path: "audit", element: <Audit />, handle: h({ crumb: "Audit" }) },
            { path: "events", element: <Events />, handle: h({ crumb: "Events" }) },
            { path: "observability", element: <Observability />, handle: h({ crumb: "Observability" }) },
          ],
        },
        { path: "*", element: <NotAvailable /> },
      ],
    },
  ];
}

export function createRouter(shell: RouteObject["element"]) {
  return createBrowserRouter(routes(shell));
}
