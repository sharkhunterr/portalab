import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../../../api/client";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Block, PluginBlocks, usePageParams } from "./Blocks";

export { ownLink } from "./Blocks";

interface Page {
  plugin: string;
  key: string;
  title_key: string;
  blocks: Block[];
}

/**
 * ``/plugins/:pluginKey/:pageKey`` (spec 023 T032, 030): a plugin page rendered from its declarative blocks
 * with design-system components only — sanitized Markdown (011), data blocks with functional states (lists,
 * tables, threads, cards), forms from a JSON Schema posting to the plugin's own action, a committing action
 * confirmed in Portalab's own dialog. No plugin JavaScript is ever executed.
 */
export default function PageRenderer() {
  const t = useT();
  const { pluginKey = "", pageKey = "" } = useParams();
  const params = usePageParams();
  const page = useQuery({
    queryKey: ["plugin-page", pluginKey, pageKey],
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/plugins/{key}/pages/{page}", {
          params: { path: { key: pluginKey, page: pageKey } },
        })
      ).data as unknown as Page,
  });
  if (page.isPending) return <FunctionalState state="loading" />;
  if (page.isError || !page.data) {
    return (
      <div className="ds-stack">
        <FunctionalState state="unavailable" label={t("plugins:page.unavailable")} />
        <Link to="/">{t("plugins:page.home")}</Link>
      </div>
    );
  }
  return (
    <div className="ds-stack">
      <PageHeader icon="plug" title={t(page.data.title_key)} />
      <PluginBlocks plugin={pluginKey} blocks={page.data.blocks} params={params} />
    </div>
  );
}
