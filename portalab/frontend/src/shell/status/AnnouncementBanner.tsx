import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useT } from "../../i18n/hooks/useT";
import { useDismissed } from "./portalStatus";
import { StatusBanner } from "./StatusBanner";

interface Banner {
  id: string;
  title: string;
  body: string;
  link: string | null;
  tone: string;
  banner_until: string | null;
  dismissible: boolean;
  created_at: string;
}

const TONES = ["info", "success", "warning", "critical"] as const;
const ICONS: Record<string, string> = {
  info: "megaphone",
  success: "sparkles",
  warning: "alert",
  critical: "alert",
};

/**
 * Announcement banner (027): an announcement the administrator chose to show « as a banner » sits across
 * the portal until its date (or until it is ended), drawn like the maintenance and incident banners — its
 * tone, title, first line of text, how long it stays and its link; each member may close it, unless the
 * administrator chose to keep it.
 */
export function AnnouncementBanner() {
  const t = useT();
  const [closed, close] = useDismissed("portalab.announcement.dismissed");
  const banners = useQuery({
    queryKey: ["announcements", "banners"],
    retry: false,
    refetchInterval: 60_000, // issue 122: an automation's banner comes and goes with what it announces
    queryFn: async () => {
      const data = (await api.GET("/api/v1/announcements/banners")).data;
      return (Array.isArray(data) ? data : []) as unknown as Banner[];
    },
  });
  const shown = (banners.data ?? []).filter((b) => !b.dismissible || !closed.includes(b.id));
  const first = shown[0];
  if (!first) return null;
  const tone = TONES.find((x) => x === first.tone) ?? "info";
  return (
    <StatusBanner
      tone={tone}
      icon={ICONS[tone] ?? "megaphone"}
      eyebrow={[t("notifications:banner.announcement")]}
      title={first.title}
      text={first.body ? first.body.split("\n")[0] : null}
      starts={first.banner_until ? first.created_at : null}
      ends={first.banner_until}
      details={first.link}
      detailsLabel={t("notifications:banner.more")}
      onClose={first.dismissible ? () => close(first.id) : undefined}
    />
  );
}
