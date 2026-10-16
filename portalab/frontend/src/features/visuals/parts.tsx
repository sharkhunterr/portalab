import { StatusBadge, type Tone } from "../../design-system/admin/AdminKit";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import type { Product } from "../marketplace/api";
import type { Economy, ElementReport, Finding, Outcome } from "./api";

/** 028: pieces shared by the pack list and the six steps of a version. */

export const LEVEL_TONE: Record<string, Tone> = { blocking: "bad", warning: "warn", info: "info" };
export const OUTCOME_TONE: Record<Outcome | "todo", Tone> = {
  done: "ok",
  warning: "warn",
  blocking: "bad",
  todo: "neutral",
};
export const OUTCOME_ICON: Record<Outcome | "todo", string> = {
  done: "check",
  warning: "alert",
  blocking: "close",
  todo: "clock",
};
export const RARITIES = ["common", "rare", "epic", "legendary"] as const;

export function param(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : String(value ?? "");
}

export function nameOf(names: Record<string, string> | null | undefined, fallback: string, language = "fr") {
  return names?.[language] || names?.fr || names?.en || fallback;
}

export function Findings({ findings }: { findings: Finding[] }) {
  const t = useT();
  if (!findings.length) return null;
  return (
    <ul className="visuals-findings">
      {findings.map((finding, index) => (
        <li
          // biome-ignore lint/suspicious/noArrayIndexKey: findings have no identity of their own
          key={index}
          data-level={finding.level}
        >
          <StatusBadge tone={LEVEL_TONE[finding.level] ?? "neutral"}>
            {t(`admin:visuals.level.${finding.level}`)}
          </StatusBadge>
          <span>
            {t(
              `admin:visuals.check.${finding.code}`,
              Object.fromEntries(Object.entries(finding.params).map(([k, v]) => [k, param(v)])),
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function OutcomeBadge({ outcome }: { outcome: Outcome | "todo" }) {
  const t = useT();
  return (
    <StatusBadge tone={OUTCOME_TONE[outcome]}>
      <Icon name={OUTCOME_ICON[outcome]} size={14} /> {t(`admin:visuals.outcome.${outcome}`)}
    </StatusBadge>
  );
}

const LOOK_FIELD: Record<string, string> = {
  level_up: "animation",
  effect: "effect",
  ambient: "ambient",
  profile_background: "background",
  avatar_frame: "frame",
  profile_banner: "banner",
  name_style: "style",
  level_badge: "style",
  notification_style: "style",
  notification_animation: "animation",
  palette: "palette",
  badge: "style",
  title: "style",
};

/** The element as a shop product, to draw it as the shop does and to try it on. */
export function asProduct(element: ElementReport, economy: Economy): Product {
  const key = LOOK_FIELD[element.type];
  const preview = { ...element.payload, ...(key && element.look ? { [key]: element.look } : {}) };
  return {
    key: element.product,
    type: element.type,
    name: nameOf(element.names, element.product),
    names: element.names,
    descriptions: element.descriptions,
    rarity: economy.rarity,
    icon: economy.icon,
    price_coins: economy.price,
    preview,
    theme: element.type === "theme" ? element.look : null,
    conditions: [],
    eligibility: [],
    config_required: false,
    featured: false,
    locked: false,
    owned: false,
    poster_effect: "none",
    repeatable: false,
    state: "available",
    version: 1,
    refund_policy: { refundable: false, window_days: 0, percent: 0 },
  } as unknown as Product;
}

/** What each element's findings are, by element (``null``: the pack's own). */
export function findingsByElement(items: Finding[], category?: "analysis" | "security") {
  const out = new Map<string | null, Finding[]>();
  for (const finding of items) {
    if (category && finding.category !== category) continue;
    out.set(finding.element, [...(out.get(finding.element) ?? []), finding]);
  }
  return out;
}
