import { AdminPage } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import { AiSettings } from "./AiSettings";
import { McpAllowlist } from "./McpAllowlist";
import "../ai.css";

/** ``/admin/ai`` (spec 018, 027 administration kit): assistant settings, usage and the MCP allow-list. */
export default function AiAdminPage() {
  const t = useT();
  return (
    <AdminPage icon="sparkles" title={t("ai:admin.title")} description={t("ai:admin.description")}>
      <AiSettings />
      <McpAllowlist />
    </AdminPage>
  );
}
