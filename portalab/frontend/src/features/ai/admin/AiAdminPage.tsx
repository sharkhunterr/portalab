import { AiSettings } from "./AiSettings";
import { McpAllowlist } from "./McpAllowlist";
import "../ai.css";

/** ``/admin/ai`` (spec 018): assistant settings, usage and the MCP allow-list. */
export default function AiAdminPage() {
  return (
    <div className="ds-stack">
      <AiSettings />
      <McpAllowlist />
    </div>
  );
}
