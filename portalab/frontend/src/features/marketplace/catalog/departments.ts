import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { Product } from "../api";
import { productTypeLabel } from "../typeLabel";

/**
 * The shop's departments (spec 015, 027 US8): themes (theme packs, interfaces, palettes), profile (banners,
 * frames, backgrounds, names, badges, titles, level badges), notifications and effects, features (widgets
 * and their settings, statistics, bonuses, project launches), packs and boosters — each a shelf per kind;
 * and the plugins' shelves among them (030).
 */
export interface Shelf {
  key: string;
  icon: string;
  types: string[];
  /** Only the products of this collection (theme packs among the packs), or all but it. */
  category?: string;
  notCategory?: string;
  /** 030: a plugin's shelf — its name in the plugin's catalog (else the name of its kind of product). */
  labelKey?: string;
  plugin?: boolean;
}

export type Department = { key: string; icon: string; shelves: Shelf[] };

export const DEPARTMENTS: Department[] = [
  {
    key: "themes",
    icon: "palette",
    shelves: [
      // a theme pack is the whole theme; an interface is the theme's look of the portal only
      { key: "themePacks", icon: "crown", types: ["bundle"], category: "ultimate" },
      { key: "interfaces", icon: "palette", types: ["theme"] },
      { key: "palettes", icon: "palette", types: ["palette"] },
    ],
  },
  {
    key: "profile",
    icon: "user",
    shelves: [
      { key: "banners", icon: "image", types: ["profile_banner", "profile_backdrop"] },
      { key: "frames", icon: "user", types: ["avatar_frame"] },
      { key: "backgrounds", icon: "sparkles", types: ["profile_background"] },
      { key: "names", icon: "feather", types: ["name_style"] },
      { key: "badges", icon: "star", types: ["badge"] },
      { key: "titles", icon: "award", types: ["title"] },
      { key: "levelBadges", icon: "trophy", types: ["level_badge"] },
    ],
  },
  {
    key: "effects",
    icon: "sparkles",
    shelves: [
      { key: "notificationStyles", icon: "bell", types: ["notification_style"] },
      { key: "notificationAnimations", icon: "bell-ring", types: ["notification_animation"] },
      { key: "ambients", icon: "snowflake", types: ["ambient"] },
      { key: "celebrations", icon: "party", types: ["effect"] },
      { key: "levelUps", icon: "trophy", types: ["level_up"] },
    ],
  },
  {
    key: "features",
    icon: "zap",
    shelves: [
      { key: "widgets", icon: "dashboard", types: ["widget"] },
      { key: "widgetOptions", icon: "settings", types: ["widget_option"] },
      { key: "statistics", icon: "chart", types: ["statistic"] },
      { key: "services", icon: "server", types: ["service_access"] }, // 027: a homelab service's access
      { key: "requests", icon: "clapperboard", types: ["special_request"] }, // 027: a film in 4K…
      { key: "community", icon: "lightbulb", types: ["project_launch"] },
      {
        key: "perks",
        icon: "rocket",
        types: ["xp_boost", "streak_freeze", "media_rescue", "radio_requests"], // #54/#55/#57, issue 184
      },
      { key: "assistant", icon: "brain", types: ["ai_capacity"] }, // issue 173: the assistant's capacities
      { key: "bonus", icon: "inbox", types: ["quota", "feature", "plugin", "access"] },
    ],
  },
  {
    key: "packs",
    icon: "shop",
    shelves: [{ key: "packs", icon: "shop", types: ["bundle"], notCategory: "ultimate" }],
  },
  // #81: sealed packs drawn at random — products like the others (a tile, a sheet), the season's first
  {
    key: "boosters",
    icon: "sparkles",
    shelves: [{ key: "boosters", icon: "sparkles", types: ["booster", "card_booster"] }],
  },
];
/** Whether a product is on a shelf: its kind, and its collection when the shelf asks for one. */
export function onShelf(shelf: Shelf, product: Product): boolean {
  return (
    shelf.types.includes(product.type) &&
    (!shelf.category || product.category === shelf.category) &&
    (!shelf.notCategory || product.category !== shelf.notCategory)
  );
}

/** The department a kind of product is in (an « in the shop » link lands on one type). */
export function departmentOf(type: string, departments: Department[] = DEPARTMENTS): string {
  return departments.find((d) => d.shelves.some((s) => s.types.includes(type)))?.key ?? "features";
}

/** The department a product is on (theme packs and other packs part ways). */
export function departmentOfProduct(product: Product, departments: Department[] = DEPARTMENTS): string {
  return departments.find((d) => d.shelves.some((s) => onShelf(s, product)))?.key ?? "features";
}

/** 030: where enabled plugins have the shop show their kinds of products (their manifests' shelves). */
export interface PluginShelf {
  key: string;
  plugin: string;
  department: string;
  label_key: string;
  icon?: string | null;
  types: string[];
}

export function usePluginShelves(): PluginShelf[] {
  const shelves = useQuery({
    queryKey: ["marketplace", "plugin-shelves"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () => ((await api.GET("/api/v1/plugins/shelves")).data ?? []) as unknown as PluginShelf[],
  });
  return Array.isArray(shelves.data) ? shelves.data : [];
}

/**
 * 030: the shop's departments with the plugins' shelves — each where its manifest puts it; a plugin's kind
 * of product no shelf holds still shows, on a shelf of its own among the features (nothing sold is hidden).
 */
export function withPluginShelves(
  departments: Department[],
  shelves: PluginShelf[],
  types: string[] = [],
): Department[] {
  const placed = new Set(departments.flatMap((d) => d.shelves.flatMap((s) => s.types)));
  const added: Array<[string, Shelf]> = [];
  for (const shelf of shelves) {
    const own = shelf.types.filter((type) => !placed.has(type));
    for (const type of own) placed.add(type);
    if (own.length) {
      added.push([
        shelf.department,
        {
          key: shelf.key,
          icon: shelf.icon ?? "sparkles",
          types: own,
          labelKey: shelf.label_key,
          plugin: true,
        },
      ]);
    }
  }
  for (const type of [...new Set(types)].sort()) {
    if (!type.startsWith("plugin:") || placed.has(type)) continue;
    placed.add(type);
    added.push(["features", { key: type, icon: "puzzle", types: [type], plugin: true }]);
  }
  if (added.length === 0) return departments;
  return departments.map((department) => {
    const own = added.filter(([key]) => key === department.key).map(([, shelf]) => shelf);
    return own.length ? { ...department, shelves: [...department.shelves, ...own] } : department;
  });
}

/** The name of a shelf: Portalab's own, or the one its plugin gives it (030). */
export function shelfLabel(
  t: (key: string, values?: Record<string, string | number>) => string,
  shelf: Shelf,
) {
  if (!shelf.plugin) return t(`marketplace:shelf.${shelf.key}`);
  const text = shelf.labelKey ? t(shelf.labelKey) : "";
  return text && text !== shelf.labelKey ? text : productTypeLabel(t, shelf.types[0] ?? shelf.key);
}
