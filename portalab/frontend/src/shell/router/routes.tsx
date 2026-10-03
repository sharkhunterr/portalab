import { lazy } from "react";
import { createBrowserRouter, type RouteObject } from "react-router";
import type { RouteHandle } from "./handle";
import { RouteErrorElement } from "./RouteBoundary";

/**
 * Route table (spec 004 T002/T019): every page is lazy-loaded (one chunk per area) inside the persistent
 * shell. Handles carry breadcrumb labels and existence sensitivity; permissions stay a UI hint (the API
 * decides). Unknown paths render "not available".
 */
const Home = lazy(() => import("../../features/dashboard/DashboardPage"));
const Account = lazy(() => import("../../pages/AccountRoute"));
const Appearance = lazy(() => import("../../pages/AppearanceRoute"));
const Privacy = lazy(() => import("../../pages/PrivacyRoute"));
const Services = lazy(() => import("../../pages/ServicesRoute"));
const ServiceDetail = lazy(() => import("../../pages/ServiceDetailRoute"));
const ControlCenter = lazy(() => import("../../pages/admin/ControlCenterRoute"));
const Configuration = lazy(() => import("../../pages/admin/ConfigurationRoute"));
const ServicesAdmin = lazy(() => import("../../pages/admin/ServicesAdminRoute"));
const Roles = lazy(() => import("../../pages/admin/RolesRoute"));
const PrivacyAdmin = lazy(() => import("../../pages/admin/PrivacyAdminRoute"));
const Audit = lazy(() => import("../../pages/admin/AuditRoute"));
const Events = lazy(() => import("../../pages/admin/EventsRoute"));
const Observability = lazy(() => import("../../pages/admin/ObservabilityRoute"));
const Incidents = lazy(() => import("../../features/support/incidents/IncidentsPage"));
const IncidentConsole = lazy(() => import("../../features/support/incidents/IncidentConsole"));
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
        {
          path: "search",
          element: <Search />,
          handle: h({ crumb: "Search", requiredPermission: "search.use" }),
        },
        { path: "account", element: <Account />, handle: h({ crumb: "Account" }) },
        { path: "settings/appearance", element: <Appearance />, handle: h({ crumb: "Appearance" }) },
        { path: "settings/language", element: <Language />, handle: h({ crumb: "Language & region" }) },
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
