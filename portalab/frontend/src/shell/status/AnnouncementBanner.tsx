import { useT } from "../../i18n/hooks/useT";
import { ANNOUNCEMENT_ICONS, announcementTone, useAnnouncementBanners, useDismissed } from "./portalStatus";
import { StatusBanner } from "./StatusBanner";

/**
 * Announcement banner (027): an announcement the administrator chose to show « as a banner » sits across
 * the portal until its date (or until it is ended), drawn like the maintenance and incident banners — its
 * tone, title, first line of text, how long it stays and its link; each member may close it, unless the
 * administrator chose to keep it (a closed one stays in the header's control center).
 */
export function AnnouncementBanner() {
  const t = useT();
  const [closed, close] = useDismissed("portalab.announcement.dismissed");
  const banners = useAnnouncementBanners();
  const shown = (banners.data ?? []).filter((b) => !b.dismissible || !closed.includes(b.id));
  const first = shown[0];
  if (!first) return null;
  const tone = announcementTone(first.tone);
  return (
    <StatusBanner
      tone={tone}
      icon={ANNOUNCEMENT_ICONS[tone]}
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
