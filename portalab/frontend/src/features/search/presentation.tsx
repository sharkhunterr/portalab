import { Icon } from "../../design-system/components/Icon";
import type { useT } from "../../i18n/hooks/useT";
import { KIND_ICONS as MEDIA_ICONS } from "../media/MediaGrid";

/**
 * #67: how a search result presents itself, in the header's suggestions and on the results page alike —
 * an icon per source, and its type and state as small badges (words first, the tone only underlines them).
 */
export const KIND_ICONS: Record<string, string> = {
  media: "film",
  wiki: "book",
  news: "newspaper",
  users: "user",
  services: "server",
  incidents: "alert",
  tickets: "ticket",
  feedback: "message",
  navigation: "compass",
  calendar: "calendar",
  community: "users",
  marketplace: "shop",
  product: "shop",
  member: "user",
  ticket: "ticket",
  incident: "alert",
  service: "server",
  campaign: "star",
  request: "plus", // #4: titles to ask for
};

/** #67: media results told apart by type — films, series, books, audiobooks, games, music… */
export function mediaGroup(type: string | undefined): { key: string; label: string; icon: string } | null {
  if (!type) return null;
  return { key: `media:${type}`, label: `search:mediaKind.${type}`, icon: MEDIA_ICONS[type] ?? "film" };
}

export interface Badge {
  label: string;
  tone: "ok" | "warn" | "bad" | "neutral";
}

interface Faceted {
  kind: string;
  facets?: Record<string, string> | null | undefined;
}

const TONES: Record<string, Badge["tone"]> = {
  available: "ok",
  published: "ok",
  resolved: "ok",
  operational: "ok",
  closed: "neutral",
  requested: "warn",
  pending: "warn",
  open: "warn",
  in_progress: "warn",
  waiting: "warn",
  investigating: "warn",
  identified: "warn",
  monitoring: "warn",
  degraded: "warn",
  draft: "neutral",
  unavailable: "bad",
  down: "bad",
  critical: "bad",
  major: "bad",
};

/** #67: a result's type and state as small badges — words first, the tone only underlines them. */
export function badgesOf(t: ReturnType<typeof useT>, item: Faceted): Badge[] {
  const facets = item.facets ?? {};
  const out: Badge[] = [];
  if ((item.kind === "media" || item.kind === "request") && facets.type)
    out.push({ label: t(`media:kind.${facets.type}`), tone: "neutral" });
  if ((item.kind === "product" || item.kind === "marketplace") && facets.type) {
    out.push({ label: t(`marketplace:type.${facets.type}`), tone: "neutral" });
  }
  const state = facets.status ?? facets.state;
  if (state) out.push({ label: stateLabel(t, state), tone: TONES[state] ?? "neutral" });
  if (facets.severity)
    out.push({ label: stateLabel(t, facets.severity), tone: TONES[facets.severity] ?? "neutral" });
  return out;
}

function stateLabel(t: ReturnType<typeof useT>, value: string): string {
  const key = `search:badge.${value}`;
  const label = t(key);
  return label === key || label === `badge.${value}` ? value.replaceAll("_", " ") : label;
}

/** #67: a facet value in words — a media or product type, a state — or the value itself when unknown. */
export function valueLabel(t: ReturnType<typeof useT>, key: string, value: string): string {
  const tries =
    key === "type" ? [`search:mediaKind.${value}`, `marketplace:type.${value}`] : [`search:badge.${value}`];
  for (const id of tries) {
    const label = t(id);
    if (label !== id && label !== id.split(":").slice(1).join(":")) return label;
  }
  return value.replaceAll("_", " ");
}

/** The badges of a result. */
export function ResultBadges({ badges }: { badges: Badge[] }) {
  if (!badges.length) return null;
  return (
    <span className="result-badges">
      {badges.map((badge) => (
        <span key={badge.label} className="result-badge" data-tone={badge.tone}>
          {badge.label}
        </span>
      ))}
    </span>
  );
}

/** A source's separator: its icon, its name and how many results it gave. */
export function SourceIcon({ kind }: { kind: string }) {
  return <Icon name={KIND_ICONS[kind] ?? "search"} size={14} />;
}
