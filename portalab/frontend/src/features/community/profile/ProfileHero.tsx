import { useQuery } from "@tanstack/react-query";
import type { CSSProperties, ReactNode } from "react";
import { api } from "../../../api/client";
import type { Ambient } from "../../../design-system/a11y/preferences";
import { Avatar } from "../../../design-system/components/Avatar";
import { LevelBadge } from "../../../design-system/components/Badges";
import { FxLayer } from "../../../design-system/components/Fx";
import { Icon } from "../../../design-system/components/Icon";
import { AmbientLayer } from "../../../design-system/themes/AmbientLayer";
import { FRAME_CLIPS, FX_NAMES, FX_STYLES, fxFrameOf } from "../../../design-system/themes/premium/fxLooks";
import { useExternalRevision } from "../../../design-system/visuals/registry";
import { useT } from "../../../i18n/hooks/useT";
import { backdropUrl, type Equipped, shownEquipped, type WornItem } from "./looks";
import { ProfileCustomizer } from "./ProfileCustomizer";
import "./profile.css";

/** A banner design (or a film backdrop) as a decorative block — shared by the hero, the picker and the shop. */
export function BannerArt({
  banner,
  backdrop,
  className,
}: Pick<Equipped, "banner" | "backdrop"> & { className?: string }) {
  const classes = className ? `${className} profile-banner` : "profile-banner";
  if (backdrop?.ref) {
    return (
      <span className={classes} data-banner="backdrop" aria-hidden="true">
        <img src={backdropUrl(backdrop.ref)} alt="" loading="lazy" />
      </span>
    );
  }
  if (banner?.startsWith("live-")) {
    // #79: an animated banner — the ambience plays inside it, for every visitor to see
    return (
      <span className={classes} data-banner="live" aria-hidden="true">
        <AmbientLayer kind={banner.slice(5) as Ambient} contained />
      </span>
    );
  }
  return <span className={classes} data-banner={banner ?? "default"} aria-hidden="true" />;
}

/** An avatar inside its frame (``none`` draws no frame). */
export function FramedAvatar({
  frame,
  name,
  userId,
  src,
  size = "xl",
}: {
  frame?: string | null | undefined;
  name: string;
  userId?: string | undefined;
  src?: string | null | undefined;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const fx = frame ? fxFrameOf(frame) : undefined;
  if (fx) {
    // #78: a frame drawn by the GPU, in a shape of its own — the avatar cut to the same shape
    const style = {
      "--frame-clip": FRAME_CLIPS[fx.shape ?? 0] ?? "none",
      "--frame-radius": fx.radius ?? "50%",
    } as CSSProperties;
    return (
      <span
        className="avatar-frame"
        data-frame={frame}
        data-size={size}
        data-fx-frame={fx.shape ?? 0}
        data-fx-cycle={fx.effect === "chrono" || undefined}
        style={style}
      >
        <FxLayer
          effect={fx.effect}
          shape={fx.shape ?? 0}
          cycle={fx.effect === "chrono"}
          className="avatar-frame__fx"
        />
        <Avatar name={name} userId={userId} src={src} size={size} decorative />
      </span>
    );
  }
  return (
    <span
      className="avatar-frame"
      data-frame={frame && frame !== "none" ? frame : undefined}
      data-size={size}
    >
      <Avatar name={name} userId={userId} src={src} size={size} decorative />
    </span>
  );
}

/** A name in the member's chosen style (font and effect). */
export function StyledName({ name, style }: { name: string; style?: string | null | undefined }) {
  const fx = style ? FX_NAMES[style] : undefined;
  return (
    <span
      className="name-style"
      data-name={style && style !== "none" ? style : undefined}
      data-fx-name={fx ? "true" : undefined}
      data-fx-cycle={fx === "chrono" || undefined}
    >
      {fx ? <FxLayer effect={fx} aura cycle={fx === "chrono"} className="fx-layer fx-layer--name" /> : null}
      {fx ? <span>{name}</span> : name}
    </span>
  );
}

/** The GPU's « pointed ends » outline: a title's ribbon. */
const TITLE_SHAPE = 6;

/** A title or badge as worn, with its animated style. */
export function WornBadge({ item, kind }: { item: WornItem; kind: "badge" | "title" }) {
  const fx = item.style ? FX_STYLES[item.style] : undefined;
  // a title is a ribbon (pointed ends), never a pill like the badges beside it
  const shape = kind === "title" ? TITLE_SHAPE : 0;
  return (
    <span
      className={kind === "badge" ? "cosmetic-badge" : "cosmetic-title"}
      data-style={item.style && item.style !== "none" ? item.style : undefined}
      data-fx={fx}
      data-fx-shape={fx && shape ? shape : undefined}
      data-fx-cycle={fx === "chrono" || undefined}
    >
      {fx ? <FxLayer effect={fx} calm shape={shape} cycle={fx === "chrono"} /> : null}
      {kind === "badge" ? <Icon name={item.icon ?? "star"} size={14} /> : null}
      {item.label}
    </span>
  );
}

/**
 * The top of a profile (027): the banner the member chose (a design, or a film's backdrop), their framed
 * avatar and name over it; on one's own profile, « Customise » opens the looks picker.
 */
export function ProfileHero({
  memberId,
  name,
  looks: worn,
  own,
  avatarSrc,
  avatarAction,
  heading = 1,
}: {
  memberId: string;
  name: string;
  looks: Equipped;
  own: boolean;
  /** #46: the picture to show (a fresh one right after a change). */
  avatarSrc?: string | null;
  /** #46: a control over the avatar (« change the picture » on the account page). */
  avatarAction?: ReactNode;
  /** The name's heading level (2 inside a page that has its own title). */
  heading?: 1 | 2;
}) {
  const t = useT();
  const Name = heading === 1 ? "h1" : "h2";
  useExternalRevision(); // 028: a pack switched off or on changes what shows
  const looks = shownEquipped(worn);
  return (
    <header className="profile-hero">
      <BannerArt banner={looks.banner ?? null} backdrop={looks.backdrop ?? null} />
      <div className="profile-hero__identity">
        <span className="profile-hero__avatar">
          <FramedAvatar
            frame={looks.frame}
            name={name}
            userId={memberId}
            src={avatarSrc === undefined ? `/api/v1/users/${memberId}/avatar` : avatarSrc}
          />
          {avatarAction}
        </span>
        <div className="profile-hero__text">
          {/* the name, its level, then the title on the same line (wrapping below on a narrow screen) */}
          <div className="profile-hero__headline">
            <Name className="profile-hero__name">
              <StyledName name={name} style={looks.name} />
              <MemberLevel memberId={memberId} look={looks.level} />
            </Name>
            {looks.title ? (
              <p className="profile-hero__title">
                <span className="visually-hidden">{t("community:looks.wornTitle")} </span>
                <WornBadge item={looks.title} kind="title" />
              </p>
            ) : null}
          </div>
          {looks.badges?.items?.length ? (
            <ul className="profile-hero__badges" aria-label={t("community:looks.wornBadges")}>
              {looks.badges.items.map((badge) => (
                <li key={badge.key}>
                  <WornBadge item={badge} kind="badge" />
                </li>
              ))}
            </ul>
          ) : null}
          {looks.backdrop?.title ? (
            <p className="profile-hero__caption">
              {t("community:looks.backdropOf", { title: looks.backdrop.title })}
            </p>
          ) : null}
        </div>
        {own ? <ProfileCustomizer name={name} memberId={memberId} /> : null}
      </div>
    </header>
  );
}

/** 027: the member's level badge in the look they wear — when their progression is visible to me. */
function MemberLevel({ memberId, look }: { memberId: string; look: string | null | undefined }) {
  const t = useT();
  const progression = useQuery({
    queryKey: ["gamification", "member-progression", memberId],
    retry: false,
    staleTime: 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/users/{user_id}/progression", {
          params: { path: { user_id: memberId } },
        })
      ).data as { level?: number } | undefined,
  });
  const level = progression.data?.level;
  if (typeof level !== "number") return null;
  return <LevelBadge level={level} label={t("shell:levelLabel", { level })} look={look ?? "classic"} />;
}
