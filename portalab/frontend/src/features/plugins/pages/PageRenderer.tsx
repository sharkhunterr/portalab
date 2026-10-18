import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { api } from "../../../api/client";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useNavigationView } from "../../../shell/nav/NavigationProvider";
import { currentEntry } from "../../../shell/nav/SectionNav";
import { isSafeMode } from "../../../shell/safeMode";
import { PluginView } from "../views/PluginView";
import { type Block, PluginBlocks, usePageParams } from "./Blocks";
import { Surface } from "./Surface";

export { ownLink } from "./Blocks";

interface Page {
  plugin: string;
  key: string;
  title_key: string;
  view?: string | null;
  /** 030: ``false`` when the plugin's view draws its own title */
  header?: boolean;
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
  // 030: the page wears its navigation entry's icon (never a « plugin » sign)
  const location = useLocation();
  const { view: navigation } = useNavigationView();
  const entry = currentEntry(navigation.sections, location.pathname);
  const { pluginKey = "", pageKey = "" } = useParams();
  const params = usePageParams();
  const [surface, setSurface] = useState<{ key: string; params: Record<string, string> } | null>(null);
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
      {page.data.header === false ? null : (
        <PageHeader icon={entry?.icon ?? "sparkles"} title={t(page.data.title_key)} />
      )}
      {page.data.view && !isSafeMode() ? (
        <PluginView
          plugin={pluginKey}
          view={page.data.view}
          params={params}
          mode="page"
          title={t(page.data.title_key)}
          onOpen={(surface, more) => setSurface({ key: surface, params: { ...params, ...more } })}
        />
      ) : (
        <PluginBlocks plugin={pluginKey} blocks={page.data.blocks} params={params} />
      )}
      {surface ? (
        <Surface
          plugin={pluginKey}
          surface={surface.key}
          params={surface.params}
          onClose={() => setSurface(null)}
        />
      ) : null}
    </div>
  );
}
