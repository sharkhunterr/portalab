import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { PluginView } from "../views/PluginView";
import { type Block, PluginBlocks } from "./Blocks";
import "../views/views.css";
import { isSafeMode } from "../../../shell/safeMode";

interface SurfaceData {
  plugin: string;
  plugin_name?: string;
  key: string;
  kind: "modal" | "drawer" | "drawer-left" | "panel";
  title_key: string;
  view?: string | null;
  position?: "bottom-right" | "bottom-left" | null;
  blocks: Block[];
}

/**
 * 030: a modal, a side drawer (either side) or a floating panel a plugin's slot, button or view opens. Its
 * frame is Portalab's (a protected surface: the plugin's name, closing); inside, Portalab's blocks or the
 * plugin's own view, given the place's parameters (a title, a conversation…).
 */
export function Surface({
  plugin,
  surface,
  params,
  onClose,
}: {
  plugin: string;
  surface: string;
  params: Record<string, string>;
  onClose: () => void;
}) {
  const t = useT();
  const [nested, setNested] = useState<{ surface: string; params: Record<string, string> } | null>(null);
  // following a link from it (a conversation, a playlist) closes it
  const location = useLocation();
  const opened = useRef(`${location.pathname}${location.search}`);
  useEffect(() => {
    if (`${location.pathname}${location.search}` !== opened.current) onClose();
  }, [location.pathname, location.search, onClose]);
  const query = useQuery({
    queryKey: ["plugin-surface", plugin, surface],
    retry: false,
    queryFn: async () =>
      // biome-ignore lint/suspicious/noExplicitAny: a route added by spec 030
      ((await api.GET(`/api/v1/plugins/${plugin}/surfaces/${surface}` as any, {})).data ??
        null) as SurfaceData | null,
  });
  const data = query.data;
  const safe = isSafeMode(); // 029: in safe mode a plugin's own view gives way to its Portalab blocks
  const title = data ? t(data.title_key) : t("plugins:page.unavailable");
  const content = (
    <div
      className={data?.view && !safe ? "plugin-surface plugin-surface--view" : "ds-stack"}
      data-plugin-surface={`${plugin}:${surface}`}
    >
      {query.isPending ? <FunctionalState state="loading" /> : null}
      {query.isError || (query.isSuccess && !data) ? <FunctionalState state="unavailable" /> : null}
      {data?.view && !safe ? (
        <PluginView
          plugin={plugin}
          view={data.view}
          params={params}
          mode="fill"
          title={title}
          onOpen={(next, nextParams) => setNested({ surface: next, params: nextParams })}
          onClose={onClose}
        />
      ) : data ? (
        <PluginBlocks plugin={plugin} blocks={data.blocks} params={params} onDone={onClose} />
      ) : null}
      {nested ? (
        <Surface
          plugin={plugin}
          surface={nested.surface}
          params={nested.params}
          onClose={() => setNested(null)}
        />
      ) : null}
    </div>
  );
  if (data?.kind === "panel") {
    // a floating panel in a corner, the page still usable around it (like a chat window)
    return (
      <section
        className="plugin-panel"
        data-corner={data.position ?? "bottom-right"}
        aria-label={title}
        data-protected=""
      >
        <header className="plugin-panel__head">
          <strong>{title}</strong>
          <span className="plugin-panel__owner">{data.plugin_name ?? plugin}</span>
          <Button variant="ghost" size="icon" aria-label={t("plugins:surface.close")} onClick={onClose}>
            <Icon name="close" />
          </Button>
        </header>
        {content}
      </section>
    );
  }
  return (
    <Dialog
      trigger={<span hidden />}
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={title}
      {...(data?.plugin_name ? { description: t("plugins:surface.by", { name: data.plugin_name }) } : {})}
      variant={data?.kind === "drawer" || data?.kind === "drawer-left" ? "drawer" : "dialog"}
      side={data?.kind === "drawer-left" ? "start" : "end"}
      size={data?.view && !safe && data.kind === "modal" ? "lg" : "md"}
      closeLabel={t("plugins:surface.close")}
    >
      {content}
    </Dialog>
  );
}
