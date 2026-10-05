import { Link, useParams } from "react-router";
import type { Ambient } from "../../../design-system/a11y/preferences";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { AmbientLayer } from "../../../design-system/themes/AmbientLayer";
import { useT } from "../../../i18n/hooks/useT";
import { useMe } from "../../auth/useAuth";
import { type CommunitySection, useProfile } from "../api";
import type { Equipped } from "./looks";
import { ProfileHero } from "./ProfileHero";
import { sectionView } from "./sections";

function SectionFrame({ memberId, section }: { memberId: string; section: CommunitySection }) {
  const t = useT();
  const View = sectionView(section.key);
  const headingId = `community-section-${section.key}`;
  const title = section.label_key ? t(section.label_key) : section.key;
  return (
    <section aria-labelledby={headingId} className="ds-card ds-stack community-section">
      <h2 id={headingId}>{title}</h2>
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
    </section>
  );
}

/**
 * ``/community/members/:memberId`` (spec 012 T008): only the sections the member's visibility lets this
 * viewer see — each in its own frame, failing alone. There is no follow, friend or message control. 027: a
 * hero on top — the member's banner (a design or a film backdrop) and framed avatar, customisable by them.
 */
export function ProfilePage() {
  const t = useT();
  const { memberId = "" } = useParams();
  const profile = useProfile(memberId);
  const me = useMe();
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
  return (
    <div className="ds-stack profile-page" data-background={looks.background ?? undefined}>
      {looks.background && looks.background !== "none" ? (
        <AmbientLayer kind={looks.background as Ambient} contained />
      ) : null}
      <ProfileHero
        memberId={memberId}
        name={profile.data.display_name ?? t("community:feed.someone")}
        looks={looks}
        own={me.data?.id === memberId}
      />
      <div className="community-sections">
        {profile.data.sections.map((section) => (
          <SectionFrame key={section.key} memberId={memberId} section={section} />
        ))}
      </div>
      <Link to="/community/members">{t("community:profile.back")}</Link>
    </div>
  );
}
