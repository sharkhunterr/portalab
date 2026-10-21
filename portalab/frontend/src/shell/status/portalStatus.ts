import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/**
 * 027: what the portal tells everyone about its state — the open incidents and the maintenances — read
 * once and shared by the header's status button, its panel and the banners.
 */
export type OpenIncident = components["schemas"]["IncidentOut"];

export interface Maintenance {
  id: string;
  title: string;
  description?: string;
  starts_at: string;
  ends_at: string;
  status: string;
  banner?: boolean;
}

export const DAY = 86_400_000;

export function useOpenIncidents() {
  return useQuery({
    queryKey: ["incidents", "open"],
    retry: false,
    refetchInterval: 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/incidents", { params: { query: { state: "open" } } })).data ??
        []) as OpenIncident[],
  });
}

export function useMaintenances() {
  return useQuery({
    queryKey: ["maintenance", "banner"],
    retry: false,
    refetchInterval: 5 * 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/maintenance")).data as unknown as { items: Maintenance[] }).items ?? [],
  });
}

/** An announcement the administrator chose to show « as a banner », while it lasts. */
export interface AnnouncementBanner {
  id: string;
  title: string;
  body: string;
  link: string | null;
  tone: string;
  banner_until: string | null;
  dismissible: boolean;
  created_at: string;
}

export const ANNOUNCEMENT_TONES = ["info", "success", "warning", "critical"] as const;
export type AnnouncementTone = (typeof ANNOUNCEMENT_TONES)[number];
export const ANNOUNCEMENT_ICONS: Record<AnnouncementTone, string> = {
  info: "megaphone",
  success: "sparkles",
  warning: "alert",
  critical: "alert",
};

export function announcementTone(tone: string): AnnouncementTone {
  return ANNOUNCEMENT_TONES.find((x) => x === tone) ?? "info";
}

export function useAnnouncementBanners() {
  return useQuery({
    queryKey: ["announcements", "banners"],
    retry: false,
    refetchInterval: 60_000, // issue 122: an automation's banner comes and goes with what it announces
    queryFn: async () => {
      const data = (await api.GET("/api/v1/announcements/banners")).data;
      return (Array.isArray(data) ? data : []) as unknown as AnnouncementBanner[];
    },
  });
}

/** A maintenance still to come or running (not cancelled), and whether it runs now. */
export function upcoming(items: Maintenance[] | undefined, within: number, now = Date.now()) {
  return (items ?? [])
    .filter(
      (m) =>
        m.status !== "cancelled" && Date.parse(m.ends_at) > now && Date.parse(m.starts_at) - now < within,
    )
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at));
}

export function isRunning(m: Maintenance, now = Date.now()): boolean {
  return Date.parse(m.starts_at) <= now && Date.parse(m.ends_at) > now;
}

/** The announcements a member closed (kept in this browser; the last ones only). */
export function useDismissed(storageKey: string) {
  const read = (): string[] => {
    try {
      return JSON.parse(window.localStorage.getItem(storageKey) ?? "[]") as string[];
    } catch {
      return [];
    }
  };
  const [closed, setClosed] = useState<string[]>(read);
  const close = (id: string) => {
    const next = [...closed, id].slice(-20);
    setClosed(next);
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {
      // no storage: closed for this visit only
    }
  };
  return [closed, close] as const;
}
