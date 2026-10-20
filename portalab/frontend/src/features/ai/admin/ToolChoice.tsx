import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { maybe } from "../../automations/labels";
import type { AiConfig } from "../api";

type Tool = AiConfig["tools"][number];
const ORDER = [
  "media",
  "support",
  "news",
  "wiki",
  "help",
  "services",
  "search",
  "navigate",
  "marketplace",
  "progression",
  "statistics",
];
const DOMAIN_ICONS: Record<string, string> = {
  media: "film",
  support: "lifebuoy",
  news: "newspaper",
  wiki: "book-open",
  help: "info",
  services: "server",
  search: "search",
  navigate: "compass",
  marketplace: "shop",
  progression: "activity",
  statistics: "chart",
};

/**
 * Issue 171 — the tools the assistant may use, in words: grouped by what they read (media, support,
 * announcements, wiki…), each with what it does and whether it reads, writes or waits for the member's
 * confirmation; on or off one by one or a whole group at once. A tool switched off is never offered to the
 * model. The administrators never let it use what is « never for the assistant ».
 */
export function ToolChoice({
  tools,
  disabled,
  onChange,
}: {
  tools: Tool[];
  disabled: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  const t = useT();
  const domainOf = (tool: Tool) => {
    const head = tool.name.split(".")[0] ?? "";
    return ORDER.includes(head) ? head : "other";
  };
  const groups = [...ORDER, "other"]
    .map((domain) => ({ domain, items: tools.filter((tool) => domainOf(tool) === domain) }))
    .filter((group) => group.items.length);
  const set = (names: string[], on: boolean) => {
    const next = new Set(disabled);
    for (const name of names) {
      if (on) next.delete(name);
      else next.add(name);
    }
    onChange(next);
  };
  return (
    <div className="ai-tools">
      <p className="admin-muted">{t("ai:admin.tools.hint")}</p>
      {groups.map(({ domain, items }) => {
        const usable = items.filter((tool) => tool.sensitivity !== "ai_forbidden").map((tool) => tool.name);
        const allOn = usable.every((name) => !disabled.has(name));
        return (
          <fieldset key={domain} className="ai-tools__group">
            <legend>
              <Icon name={DOMAIN_ICONS[domain] ?? "plug"} size={16} />{" "}
              {maybe(t, `ai:admin.domain.${domain}`, domain)}
              <button type="button" className="ai-tools__all" onClick={() => set(usable, !allOn)}>
                {allOn ? t("ai:admin.tools.none") : t("ai:admin.tools.all")}
              </button>
            </legend>
            {items.map((tool) => (
              <label key={tool.name} className="ai-tool" data-off={disabled.has(tool.name) || undefined}>
                <input
                  type="checkbox"
                  checked={!disabled.has(tool.name)}
                  disabled={tool.sensitivity === "ai_forbidden"}
                  onChange={(event) => set([tool.name], event.target.checked)}
                />
                <span className="ai-tool__text">
                  <span className="ai-tool__name">
                    {maybe(t, `ai:tool.${tool.name}.label`, tool.name)}
                    <span className="ai-tool__badge" data-sensitivity={tool.sensitivity}>
                      {t(`ai:admin.sensitivity.${tool.sensitivity}`)}
                    </span>
                  </span>
                  <span className="ai-tool__hint">
                    {maybe(t, `ai:tool.${tool.name}.hint`, tool.description ?? "")}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        );
      })}
    </div>
  );
}
