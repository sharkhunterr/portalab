import type { CSSProperties } from "react";
import { Link } from "react-router";
import { Avatar } from "../../design-system/components/Avatar";
import {
  CoinBadge,
  compactNumber,
  LevelBadge,
  levelProgress,
  ProgressBar,
} from "../../design-system/components/Badges";
import { FxLayer } from "../../design-system/components/Fx";
import { Icon } from "../../design-system/components/Icon";
import { FRAME_CLIPS, fxFrameOf } from "../../design-system/themes/premium/fxLooks";
import { useProfileLooks } from "../../features/community/profile/looks";
import { BannerArt } from "../../features/community/profile/ProfileHero";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { useShellStrings } from "../strings";
import type { PersonalEntry } from "./PersonalMenu";
import type { useHeaderData } from "./useHeaderData";

/**
 * The member at the top of the navigation (027): avatar and name (to the profile), level with its progress
 * bar, Coins and contribution — dressed in the banner (or film backdrop) and avatar frame they wear on their
 * profile (#75). In the phone menu — where the header keeps only what matters most — it also
 * carries the personal destinations and sign out that the avatar menu offers elsewhere.
 */
export function ProfileCard({
  data,
  personal = [],
  onNavigate,
  onSignOut,
}: {
  data: ReturnType<typeof useHeaderData>;
  /** Given in the phone menu: the personal destinations, then sign out. */
  personal?: readonly PersonalEntry[];
  onNavigate?: () => void;
  onSignOut?: () => void;
}) {
  const t = useT();
  const strings = useShellStrings();
  const { locale } = useLocaleContext();
  const me = data.me;
  const worn = useProfileLooks(Boolean(me)).data?.equipped;
  if (!me) return null;
  const frame = worn?.frame && worn.frame !== "none" ? worn.frame : undefined;
  const name = me.display_name ?? me.login ?? "";
  const progression = data.progression;
  const profile = `/community/members/${me.id}`;
  const next = progression?.next_level_at ?? null;
  const ratio = progression ? levelProgress(progression.xp, progression.level_floor, next) : 0;
  const progressLabel = progression
    ? next === null
      ? t("shell:levelMax", { level: progression.level })
      : t("shell:levelProgress", {
          level: progression.level,
          xp: progression.xp - progression.level_floor,
          next: next - progression.level_floor,
        })
    : "";
  return (
    <section className="shell-profile" aria-label={strings.profile}>
      {worn?.backdrop?.ref || worn?.banner ? (
        // the same art as the profile's — a film backdrop, a design, or an animated banner (#79)
        <BannerArt
          className="shell-profile__banner"
          banner={worn.banner ?? null}
          backdrop={worn.backdrop ?? null}
        />
      ) : null}
      <Link to={profile} className="shell-profile__who" onClick={onNavigate}>
        {frame && fxFrameOf(frame) ? (
          <span
            className="avatar-frame"
            data-frame={frame}
            data-fx-frame={fxFrameOf(frame)?.shape ?? 0}
            data-fx-cycle={fxFrameOf(frame)?.effect === "chrono" || undefined}
            style={
              {
                "--frame-clip": FRAME_CLIPS[fxFrameOf(frame)?.shape ?? 0] ?? "none",
                "--frame-radius": fxFrameOf(frame)?.radius ?? "50%",
              } as CSSProperties
            }
          >
            <FxLayer
              effect={fxFrameOf(frame)?.effect ?? "blaze"}
              shape={fxFrameOf(frame)?.shape ?? 0}
              cycle={fxFrameOf(frame)?.effect === "chrono"}
              className="avatar-frame__fx"
            />
            <Avatar name={name} userId={me.id} src={data.avatarUrl} size="lg" decorative />
          </span>
        ) : (
          <span className="avatar-frame" data-frame={frame}>
            <Avatar name={name} userId={me.id} src={data.avatarUrl} size="lg" decorative />
          </span>
        )}
        <span className="shell-profile__name">
          <strong>{name}</strong>
          <span>{strings.profile}</span>
        </span>
      </Link>
      {progression ? (
        <Link to="/progression" className="shell-profile__progress" onClick={onNavigate}>
          <span className="shell-profile__level">
            <LevelBadge
              level={progression.level}
              label={t("shell:levelLabel", { level: progression.level })}
            />
            <span className="shell-profile__bar">
              <ProgressBar value={ratio} label={progressLabel} size="sm" />
            </span>
          </span>
          <span className="shell-profile__stats">
            <CoinBadge amount={progression.coins} label={strings.coins} locale={locale} />
            <span
              className="shell-profile__stat"
              role="img"
              aria-label={`${t("shell:contribution")}: ${new Intl.NumberFormat(locale).format(progression.contribution)}`}
            >
              <Icon name="handshake" size={16} />
              <span aria-hidden="true">{compactNumber(progression.contribution, locale)}</span>
            </span>
          </span>
        </Link>
      ) : null}
      {onSignOut ? (
        <ul className="shell-profile__links">
          {personal
            .filter((entry) => entry.route && entry.route !== profile)
            .map((entry) => (
              <li key={entry.key}>
                <Link to={entry.route as string} onClick={onNavigate}>
                  <Icon name={entry.icon ?? "chevron-right"} size={16} />
                  {strings.label(entry.label_key)}
                </Link>
              </li>
            ))}
          <li>
            <button type="button" onClick={onSignOut}>
              <Icon name="logout" size={16} />
              {strings.signOut}
            </button>
          </li>
        </ul>
      ) : null}
    </section>
  );
}
