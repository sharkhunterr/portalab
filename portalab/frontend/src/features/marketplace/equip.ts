import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { UiPreferences } from "../../design-system/a11y/preferences";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import { type Slot, useEquipLook, useProfileLooks } from "../community/profile/looks";
import type { Product } from "./api";

/**
 * 027: what a product puts on and whether it is worn now — the shop marks it « Equipped » and offers
 * « Equip » for what is owned but not worn. Interface looks are the member's appearance preferences
 * (``theme`` counts when the active theme brings that very look); profile looks are worn through the
 * profile-looks API (a badge joins the showcase, in front).
 */
type PreferenceKey = Extract<
  keyof UiPreferences,
  "theme" | "palette" | "ambient" | "celebration" | "notificationStyle" | "notificationAnimation" | "levelUp"
>;

const PREFERENCES: Record<string, [PreferenceKey, string]> = {
  theme: ["theme", "theme"],
  palette: ["palette", "palette"],
  ambient: ["ambient", "ambient"],
  effect: ["celebration", "effect"],
  notification_style: ["notificationStyle", "style"],
  notification_animation: ["notificationAnimation", "animation"],
  level_up: ["levelUp", "animation"],
};
const SLOTS: Record<string, [Slot, string | null]> = {
  profile_banner: ["banner", "banner"],
  avatar_frame: ["frame", "frame"],
  profile_background: ["background", "background"],
  name_style: ["name", "style"],
  level_badge: ["level", "style"],
  title: ["title", null],
  badge: ["badges", null],
};
const SHOWCASE = 3;

export interface Equipment {
  /** Whether this product can be worn at all (a look, not a service or a pack). */
  wearable: (product: Product) => boolean;
  equipped: (product: Product) => boolean;
  equip: (product: Product) => Promise<void>;
  pending: boolean;
}

export function useEquipment(): Equipment {
  const { preferences, setPreference } = usePreferences();
  const { looks } = useTheme();
  const profile = useProfileLooks();
  const wear = useEquipLook();
  const worn = profile.data?.equipped;
  const lookOf = (product: Product, field: string | null): string | null => {
    const preview = (product.preview ?? {}) as Record<string, unknown>;
    return field && typeof preview[field] === "string" ? (preview[field] as string) : null;
  };
  const wearable = (product: Product) => product.type in PREFERENCES || product.type in SLOTS;
  const equipped = (product: Product) => {
    const preference = PREFERENCES[product.type];
    if (preference) {
      const [key, field] = preference;
      const value = lookOf(product, field);
      if (!value) return false;
      const chosen = preferences[key] as string | null;
      if (chosen === value) return true;
      // « follow the theme »: worn when the active theme brings this very look
      return (
        chosen === "theme" &&
        key !== "theme" &&
        key !== "palette" &&
        looks[key as keyof typeof looks] === value
      );
    }
    const slot = SLOTS[product.type];
    if (!slot || !worn) return false;
    const [name, field] = slot;
    if (name === "title") return worn.title?.key === product.key;
    if (name === "badges") return (worn.badges?.items ?? []).some((item) => item.key === product.key);
    return (worn[name] as string | null | undefined) === lookOf(product, field);
  };
  const equip = async (product: Product) => {
    const preference = PREFERENCES[product.type];
    if (preference) {
      const [key, field] = preference;
      const value = lookOf(product, field);
      if (value) setPreference(key, value as never);
      return;
    }
    const slot = SLOTS[product.type];
    if (!slot) return;
    const [name, field] = slot;
    if (name === "title") return void (await wear.mutateAsync({ slot: name, value: product.key }));
    if (name === "badges") {
      const current = (worn?.badges?.items ?? [])
        .map((item) => item.key)
        .filter((key) => key !== product.key);
      return void (await wear.mutateAsync({
        slot: name,
        value: [product.key, ...current].slice(0, SHOWCASE),
      }));
    }
    const value = lookOf(product, field);
    if (value) await wear.mutateAsync({ slot: name, value });
  };
  return { wearable, equipped, equip, pending: wear.isPending };
}
