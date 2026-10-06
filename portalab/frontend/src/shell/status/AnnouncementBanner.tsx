import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";

interface Banner {
  id: string;
  title: string;
  body: string;
  link: string | null;
  tone: string;
}

const DISMISSED = "portalab.announcement.dismissed";
const ICONS: Record<string, string> = {
  info: "megaphone",
  success: "sparkles",
  warning: "alert",
  critical: "alert",
};

function dismissed(): string[] {
  try {
    return JSON.parse(window.localStorage.getItem(DISMISSED) ?? "[]") as string[];
  } catch {
    return [];
  }
}

/**
 * Announcement banner (027): an announcement the administrator chose to show « as a banner » sits across
 * the portal until its date (or until it is ended) — its tone, title, text and link; each member may close
 * it (a critical one cannot be closed).
 */
export function AnnouncementBanner() {
  const t = useT();
  const [closed, setClosed] = useState<string[]>(dismissed);
  const banners = useQuery({
    queryKey: ["announcements", "banners"],
    retry: false,
    refetchInterval: 5 * 60_000,
    queryFn: async () => {
      const data = (await api.GET("/api/v1/announcements/banners")).data;
      return (Array.isArray(data) ? data : []) as unknown as Banner[];
    },
  });
  const shown = (banners.data ?? []).filter((b) => b.tone === "critical" || !closed.includes(b.id));
  const first = shown[0];
  if (!first) return null;
  const close = () => {
    const next = [...closed, first.id].slice(-30);
    setClosed(next);
    try {
      window.localStorage.setItem(DISMISSED, JSON.stringify(next));
    } catch {
      // no storage: closed for this visit only
    }
  };
  return (
    <div className="announcement-banner" role="status" data-tone={first.tone}>
      <Icon name={ICONS[first.tone] ?? "megaphone"} size={18} />
      <span className="announcement-banner__text">
        <strong>{first.title}</strong>
        {first.body ? <span> · {first.body.split("\n")[0]}</span> : null}
      </span>
      {first.link ? <Link to={first.link}>{t("notifications:banner.more")}</Link> : null}
      {first.tone !== "critical" ? (
        <button
          type="button"
          className="maintenance-banner__close"
          onClick={close}
          aria-label={t("notifications:banner.close")}
        >
          <Icon name="close" size={16} />
        </button>
      ) : null}
    </div>
  );
}
