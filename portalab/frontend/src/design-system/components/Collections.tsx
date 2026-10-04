import type { ReactNode } from "react";
import { Icon } from "./Icon";

/**
 * Collection building blocks (spec 027 FR-024, R20): artwork-forward tiles for media/products/projects/
 * achievements, list items with a leading avatar or icon, and statistic figures. Imagery always has a
 * graceful fallback (gradient + icon) so a missing poster never leaves a hole.
 */

export interface TileProps {
  title: string;
  subtitle?: ReactNode;
  image?: string | null;
  /** Fallback icon when there is no image. */
  icon?: string;
  badges?: ReactNode;
  href?: string;
  onSelect?: () => void;
  aspect?: "poster" | "square" | "wide";
  footer?: ReactNode;
}

export function Tile({
  title,
  subtitle,
  image,
  icon = "image",
  badges,
  href,
  onSelect,
  aspect = "poster",
  footer,
}: TileProps) {
  const media = (
    <div className="ds-tile__media" data-aspect={aspect}>
      {image ? (
        <img src={image} alt="" loading="lazy" />
      ) : (
        <span className="ds-tile__fallback" aria-hidden="true">
          <Icon name={icon} size={36} />
        </span>
      )}
      {badges ? <div className="ds-tile__badges">{badges}</div> : null}
    </div>
  );
  const body = (
    <div className="ds-tile__body">
      <span className="ds-tile__title">{title}</span>
      {subtitle ? <span className="ds-tile__subtitle">{subtitle}</span> : null}
    </div>
  );
  return (
    <article className="ds-tile">
      {href ? (
        <a className="ds-tile__link" href={href}>
          {media}
          {body}
        </a>
      ) : onSelect ? (
        <button type="button" className="ds-tile__link" onClick={onSelect}>
          {media}
          {body}
        </button>
      ) : (
        <div className="ds-tile__link">
          {media}
          {body}
        </div>
      )}
      {footer ? <div className="ds-tile__footer">{footer}</div> : null}
    </article>
  );
}

export function TileGrid({
  label,
  children,
  size = "md",
}: {
  label: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <ul className="ds-tile-grid" data-size={size} aria-label={label}>
      {Array.isArray(children) ? (
        children.map((child, index) => <li key={(child as { key?: string })?.key ?? index}>{child}</li>)
      ) : (
        <li>{children}</li>
      )}
    </ul>
  );
}

export interface ListItemProps {
  leading?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  trailing?: ReactNode;
  href?: string;
}

export function ListItem({ leading, title, meta, trailing, href }: ListItemProps) {
  const main = (
    <>
      {leading ? <span className="ds-list-item__leading">{leading}</span> : null}
      <span className="ds-list-item__main">
        <span className="ds-list-item__title">{title}</span>
        {meta ? <span className="ds-list-item__meta">{meta}</span> : null}
      </span>
    </>
  );
  return (
    <li className="ds-list-item">
      {href ? (
        <a className="ds-list-item__link" href={href}>
          {main}
        </a>
      ) : (
        <div className="ds-list-item__link">{main}</div>
      )}
      {trailing ? <span className="ds-list-item__trailing">{trailing}</span> : null}
    </li>
  );
}

export function StatFigure({
  label,
  value,
  icon,
  trend,
}: {
  label: string;
  value: ReactNode;
  icon?: string;
  trend?: { direction: "up" | "down" | "flat"; text: string };
}) {
  return (
    <div className="ds-stat">
      <span className="ds-stat__label">
        {icon ? <Icon name={icon} size={16} /> : null}
        {label}
      </span>
      <span className="ds-stat__value">{value}</span>
      {trend ? (
        <span className="ds-stat__trend" data-direction={trend.direction}>
          {trend.text}
        </span>
      ) : null}
    </div>
  );
}
