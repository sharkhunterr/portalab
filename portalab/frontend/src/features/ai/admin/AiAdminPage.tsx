import { AdminPage } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import { AiDashboard } from "./AiDashboard";
import { IdentitySettings, ModelSettings, ShopSettings, ToolSettings } from "./AiSettings";
import { McpAllowlist } from "./McpAllowlist";
import "../ai.css";

export type AiAdminView = "dashboard" | "model" | "identity" | "tools" | "shop";

const ICONS: Record<AiAdminView, string> = {
  dashboard: "chart",
  model: "brain",
  identity: "sparkles",
  tools: "wrench",
  shop: "shop",
};

/**
 * ``/admin/ai`` (spec 018, 027 administration kit; issue 176: the assistant's hub) — its dashboard, then one
 * page each for its model, its identity and instructions, and its tools (the portal's and the MCP servers').
 */
export default function AiAdminPage({ view = "dashboard" }: { view?: AiAdminView }) {
  const t = useT();
  return (
    <AdminPage
      icon={ICONS[view]}
      title={t(`ai:admin.page.${view}`)}
      description={t(`ai:admin.page.${view}Hint`)}
      wide={view === "dashboard"}
    >
      {view === "dashboard" ? <AiDashboard /> : null}
      {view === "model" ? <ModelSettings /> : null}
      {view === "identity" ? <IdentitySettings /> : null}
      {view === "shop" ? <ShopSettings /> : null}
      {view === "tools" ? (
        <>
          <ToolSettings />
          <McpAllowlist />
        </>
      ) : null}
    </AdminPage>
  );
}
