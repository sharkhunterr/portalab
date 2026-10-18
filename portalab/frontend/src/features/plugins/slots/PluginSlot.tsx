import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { connectStream } from "../../../api/stream";
import { Button } from "../../../design-system/components/Button";
import { CountBadge } from "../../../design-system/components/CountBadge";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { isSafeMode } from "../../../shell/safeMode";
import { ownLink } from "../pages/Blocks";
import { Surface } from "../pages/Surface";
import { PluginView } from "../views/PluginView";

/** What an enabled plugin adds to a place of Portalab's screens, for this member (spec 030, slots). */
export interface Contribution {
  id: string;
  plugin: string;
  slot: string;
  key: string;
  label_key: string;
  icon?: string | null;
  opens?: string | null;
  link?: string | null;
  badge?: string | null;
  live?: string | null;
  /** its own look: a view of the plugin drawn in a sandbox at the slot (a launcher) */
  view?: string | null;
  size?: { width?: number; height?: number } | null;
  corner?: "bottom-right" | "bottom-left" | null;
}

export function useContributions() {
  return useQuery({
    queryKey: ["plugin-slots"],
    staleTime: 60_000,
    retry: false,
    queryFn: async () => {
      try {
        // biome-ignore lint/suspicious/noExplicitAny: a route added by spec 030
        const data = (await api.GET("/api/v1/plugins/slots" as any, {})).data;
        return (Array.isArray(data) ? data : []) as Contribution[];
      } catch {
        return [] as Contribution[]; // plugins unavailable: Portalab's screens stay as they are
      }
    },
  });
}

function useBadge(contribution: Contribution): number {
  const query = useQuery({
    queryKey: ["plugin-badge", contribution.id],
    enabled: Boolean(contribution.badge),
    refetchInterval: 60_000,
    queryFn: async () => {
      const path = `/api/v1/plugins/${contribution.plugin}/${contribution.badge}`;
      // biome-ignore lint/suspicious/noExplicitAny: plugin routes are declared at runtime
      const data = (await api.GET(path as any, {})).data as { value?: number; count?: number } | undefined;
      return Math.max(0, Math.floor(Number(data?.count ?? data?.value ?? 0))) || 0;
    },
  });
  const { refetch } = query;
  useEffect(() => {
    if (!contribution.live) return undefined;
    const handle = connectStream({ topics: [contribution.live], onEvent: () => void refetch() });
    return () => handle.close();
  }, [contribution.live, refetch]);
  return query.data ?? 0;
}

function SlotButton({
  contribution,
  params,
  compact,
  floating = false,
}: {
  contribution: Contribution;
  params: Record<string, string>;
  compact: boolean;
  floating?: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const count = useBadge(contribution);
  const label = t(contribution.label_key);
  const link = ownLink(contribution.plugin, contribution.link);
  const [surface, setSurface] = useState<{ key: string; params: Record<string, string> } | null>(null);
  if (contribution.view && !isSafeMode()) {
    // the plugin draws its own launcher; it opens its surfaces through Portalab
    return (
      <>
        <PluginView
          plugin={contribution.plugin}
          view={contribution.view}
          params={params}
          mode="launcher"
          title={label}
          size={contribution.size ?? null}
          onOpen={(key, more) => setSurface({ key, params: { ...params, ...more } })}
        />
        {surface ? (
          <Surface
            plugin={contribution.plugin}
            surface={surface.key}
            params={surface.params}
            onClose={() => setSurface(null)}
          />
        ) : null}
      </>
    );
  }
  const content = (
    <>
      <Icon name={contribution.icon ?? "plug"} />
      {compact ? null : <span>{label}</span>}
      {count ? <CountBadge count={count} label={label} /> : null}
    </>
  );
  if (!contribution.opens && link) {
    return (
      <Link
        to={link}
        className={`ds-button ds-button--ghost${compact ? " ds-button--icon" : ""}`}
        aria-label={compact ? label : undefined}
      >
        {content}
      </Link>
    );
  }
  return (
    <>
      <Button
        variant={floating ? "primary" : compact ? "ghost" : "secondary"}
        size={compact ? "icon" : undefined}
        className={floating ? "plugin-corner__button" : undefined}
        aria-label={compact ? label : undefined}
        data-plugin-slot={contribution.id}
        onClick={() => setOpen(true)}
      >
        {content}
      </Button>
      {open && contribution.opens ? (
        <Surface
          plugin={contribution.plugin}
          surface={contribution.opens}
          params={params}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

/**
 * 030: a place of Portalab's screens plugins may add to (``media.actions``, ``header.action``…). What they add
 * is drawn here by Portalab — a button, an icon with a count — and opens their modal or drawer, or one of
 * their pages; ``params`` is what the place gives them (a title's id). Nothing shows when no plugin adds to it.
 */
export function PluginSlot({
  name,
  params = {},
  compact = false,
}: {
  name: string;
  params?: Record<string, string>;
  compact?: boolean;
}) {
  const contributions = useContributions();
  const here = (contributions.data ?? []).filter((c) => c.slot === name);
  if (!here.length) return null;
  return (
    <>
      {here.map((contribution) => (
        <SlotButton key={contribution.id} contribution={contribution} params={params} compact={compact} />
      ))}
    </>
  );
}

/**
 * 030: what plugins place in a corner of every screen (a messenger's button, bottom right or left): their own
 * launcher view, or Portalab's round button with their icon and count, opening their panel or drawer.
 */
export function PluginCorners() {
  const contributions = useContributions();
  const corners = (contributions.data ?? []).filter((c) => c.slot === "corner");
  if (!corners.length) return null;
  return (
    <>
      {(["bottom-right", "bottom-left"] as const).map((corner) => {
        const here = corners.filter((c) => (c.corner ?? "bottom-right") === corner);
        return here.length ? (
          <div key={corner} className="plugin-corner" data-corner={corner}>
            {here.map((contribution) => (
              <SlotButton key={contribution.id} contribution={contribution} params={{}} compact floating />
            ))}
          </div>
        ) : null;
      })}
    </>
  );
}
