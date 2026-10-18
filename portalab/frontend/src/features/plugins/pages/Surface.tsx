import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useLocation } from "react-router";
import { api } from "../../../api/client";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Block, PluginBlocks } from "./Blocks";

interface SurfaceData {
  plugin: string;
  key: string;
  kind: "modal" | "drawer";
  title_key: string;
  blocks: Block[];
}

/**
 * 030: a modal or a side drawer a plugin's slot or button opens — Portalab's own dialog (a protected
 * surface), the plugin's blocks inside, the place's parameters (a title, a playlist…) given to them.
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
  const title = query.data ? t(query.data.title_key) : t("plugins:page.unavailable");
  return (
    <Dialog
      trigger={<span hidden />}
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={title}
      variant={query.data?.kind === "drawer" ? "drawer" : "dialog"}
      closeLabel={t("plugins:surface.close")}
    >
      <div className="ds-stack" data-plugin-surface={`${plugin}:${surface}`}>
        {query.isPending ? <FunctionalState state="loading" /> : null}
        {query.isError || (query.isSuccess && !query.data) ? <FunctionalState state="unavailable" /> : null}
        {query.data ? (
          <PluginBlocks plugin={plugin} blocks={query.data.blocks} params={params} onDone={onClose} />
        ) : null}
      </div>
    </Dialog>
  );
}
