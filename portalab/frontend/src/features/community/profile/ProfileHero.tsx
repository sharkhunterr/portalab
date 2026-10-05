import { Avatar } from "../../../design-system/components/Avatar";
import { useT } from "../../../i18n/hooks/useT";
import "../../../design-system/themes/cosmetics.css";
import { backdropUrl, type Equipped } from "./looks";
import { ProfileCustomizer } from "./ProfileCustomizer";
import "./profile.css";

/** A banner design (or a film backdrop) as a decorative block — shared by the hero, the picker and the shop. */
export function BannerArt({ banner, backdrop }: Pick<Equipped, "banner" | "backdrop">) {
  if (backdrop?.ref) {
    return (
      <span className="profile-banner" data-banner="backdrop" aria-hidden="true">
        <img src={backdropUrl(backdrop.ref)} alt="" loading="lazy" />
      </span>
    );
  }
  return <span className="profile-banner" data-banner={banner ?? "default"} aria-hidden="true" />;
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
  size?: "md" | "lg" | "xl";
}) {
  return (
    <span className="avatar-frame" data-frame={frame && frame !== "none" ? frame : undefined}>
      <Avatar name={name} userId={userId} src={src} size={size} decorative />
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
  looks,
  own,
}: {
  memberId: string;
  name: string;
  looks: Equipped;
  own: boolean;
}) {
  const t = useT();
  return (
    <header className="profile-hero">
      <BannerArt banner={looks.banner ?? null} backdrop={looks.backdrop ?? null} />
      <div className="profile-hero__identity">
        <FramedAvatar
          frame={looks.frame}
          name={name}
          userId={memberId}
          src={`/api/v1/users/${memberId}/avatar`}
        />
        <div className="profile-hero__text">
          <h1>{name}</h1>
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
