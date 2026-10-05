import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";

/**
 * Profile looks (027): the banner, the avatar frame and the film backdrop a member wears — the designs
 * sold in the shop and not owned come back locked (the server refuses them anyway).
 */
export interface LookChoice {
  key: string;
  locked: boolean;
}

export interface Backdrop {
  object_id: string;
  ref: string;
  title?: string;
}

/** A title or badge as worn: its label, icon and animated style. */
export interface WornItem {
  key: string;
  label: string;
  icon?: string | null;
  style?: string | null;
}

export interface Equipped {
  banner?: string | null;
  frame?: string | null;
  backdrop?: Backdrop | null;
  /** 027: an animated background behind the profile, the name's style, a title, a badge showcase. */
  background?: string | null;
  name?: string | null;
  title?: WornItem | null;
  badges?: { items: WornItem[] } | null;
}

export type Slot = "banner" | "frame" | "backdrop" | "background" | "name" | "title" | "badges";

export interface LooksCatalog {
  banners: LookChoice[];
  frames: LookChoice[];
  backgrounds: LookChoice[];
  names: LookChoice[];
  titles: WornItem[];
  badges: WornItem[];
  backdrop: { unlocked: boolean };
  equipped: Equipped;
}

const KEY = ["marketplace", "profile-looks"] as const;

export function useProfileLooks(enabled = true) {
  return useQuery({
    queryKey: KEY,
    enabled,
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/me/profile-looks")).data as unknown as LooksCatalog,
  });
}

export function useEquipLook() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ slot, value }: { slot: Slot; value: unknown }) =>
      (await api.PUT("/api/v1/me/profile-looks", { body: { slot, value } })).data,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["community"] });
    },
  });
}

export function backdropUrl(ref: string, size = "w1280"): string {
  return `/api/v1/media/metadata-images?ref=${encodeURIComponent(ref)}&size=${size}`;
}
