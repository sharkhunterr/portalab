import { useState } from "react";
import { Link, useParams } from "react-router";
import type { Ambient } from "../../../design-system/a11y/preferences";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { AmbientLayer } from "../../../design-system/themes/AmbientLayer";
import { useT } from "../../../i18n/hooks/useT";
import { SettingsCard } from "../../account/SettingsKit";
import { PhotoControl, ProfileCard } from "../../auth/ProfileEditor";
import { useMe } from "../../auth/useAuth";
import { type CommunitySection, useProfile } from "../api";
import type { Equipped } from "./looks";
import { ProfileHero } from "./ProfileHero";
import { sectionView } from "./sections";

/** #46: each section's icon, its card drawn like the « My account » tabs. */
const ICONS: Record<string, string> = {
  identity: "user",
  progression: "trophy",
  achievements: "medal",
  activity: "activity",
  projects: "lightbulb",
  cosmetics: "sparkles",
};

function SectionFrame({ memberId, section }: { memberId: string; section: CommunitySection }) {
  const t = useT();
  const View = sectionView(section.key);
  const title = section.label_key ? t(section.label_key) : section.key;
  return (
    <SettingsCard icon={ICONS[section.key] ?? "star"} title={title} level={2} data-section={section.key}>
      {section.state === "available" || section.state === "stale" ? (
        <>
          {section.state === "stale" ? (
            <FunctionalState state="stale" label={t("community:section.stale")} />
          ) : null}
          <View memberId={memberId} data={section.data as Record<string, unknown>} />
        </>
      ) : section.state === "no-data" ? (
        <FunctionalState state="no-data" label={t("community:section.noData")} />
      ) : (
        <FunctionalState state="unavailable" label={t("community:section.unavailable")} />
      )}
    </SettingsCard>
  );
}

/**
 * A member's profile (spec 012 T008): only the sections the member's visibility lets this viewer see —
 * each in its own frame, failing alone; no follow, friend or message control. 027: a hero on top — the
 * member's banner and framed avatar, customisable by them. #51: on one's own profile, the picture changes
 * from the avatar and the profile card (name, « About me ») sits with the sections — the same view in
 * My account.
 */
export function MemberProfile({
  memberId,
  heading = 1,
  withBackground = true,
}: {
  memberId: string;
  heading?: 1 | 2;
  /** #79: the animated background is for the profile page; on « My account » the portal's ambience stays alone */
  withBackground?: boolean;
}) {
  const t = useT();
  const profile = useProfile(memberId);
  const me = useMe();
  const [version, setVersion] = useState(0);
  if (profile.isPending) return <FunctionalState state="loading" />;
  if (profile.isError) return <FunctionalState state="unavailable" onRetry={() => profile.refetch()} />;
  if (!profile.data) {
    return (
      <div className="ds-stack">
        <p>{t("community:profile.notFound")}</p>
        <Link to="/community/members">{t("community:profile.back")}</Link>
      </div>
    );
  }
  const looks = (profile.data.looks ?? {}) as Equipped;
  const own = me.data?.id === memberId ? me.data : null;
  const avatar = own
    ? own.has_avatar
      ? `/api/v1/users/${memberId}/avatar${version ? `?v=${version}` : ""}`
      : null
    : undefined;
  return (
    <div
      className="ds-stack profile-page"
      data-background={withBackground ? (looks.background ?? undefined) : undefined}
    >
      {withBackground && looks.background && looks.background !== "none" ? (
        <AmbientLayer kind={looks.background as Ambient} contained />
      ) : null}
      <ProfileHero
        memberId={memberId}
        name={own?.display_name ?? profile.data.display_name ?? t("community:feed.someone")}
        looks={looks}
        own={Boolean(own)}
        heading={heading}
        {...(avatar !== undefined ? { avatarSrc: avatar } : {})}
        {...(own ? { avatarAction: <PhotoControl onChanged={() => setVersion(Date.now())} /> } : {})}
      />
      <div className="community-sections">
        {own ? (
          <div data-section="edit" className="community-sections__edit">
            <ProfileCard me={own} onPhotoRemoved={() => setVersion(Date.now())} />
          </div>
        ) : null}
        {(profile.data.sections ?? []).map((section) => (
          <SectionFrame key={section.key} memberId={memberId} section={section} />
        ))}
      </div>
    </div>
  );
}

/** ``/community/members/:memberId``. */
export function ProfilePage() {
  const t = useT();
  const { memberId = "" } = useParams();
  return (
    <>
      <MemberProfile memberId={memberId} />
      <Link to="/community/members">{t("community:profile.back")}</Link>
    </>
  );
}
