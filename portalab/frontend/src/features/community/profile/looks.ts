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

export interface Equipped {
  banner?: string | null;
  frame?: string | null;
  backdrop?: Backdrop | null;
}

export interface LooksCatalog {
  banners: LookChoice[];
  frames: LookChoice[];
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
    mutationFn: async ({ slot, value }: { slot: "banner" | "frame" | "backdrop"; value: unknown }) =>
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
