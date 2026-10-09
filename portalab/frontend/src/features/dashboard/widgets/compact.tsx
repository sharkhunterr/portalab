import type { ReactNode } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import "./compact.css";

/**
 * 027 (#36): a widget's compact form — what it says on a single row, the same everywhere: a picture (or an
 * icon), a title, a detail line, and something at the end (a figure, a button). The line opens ``to``; the
 * end stays outside the link (it may be a button).
 */
export function CompactLine({
  to,
  image,
  icon,
  title,
  detail,
  end,
}: {
  to?: string | null | undefined;
  image?: string | null | undefined;
  icon?: string | undefined;
  title: ReactNode;
  detail?: ReactNode;
  end?: ReactNode;
}) {
  const body = (
    <>
      {image ? (
        <img className="compact-line__image" src={image} alt="" loading="lazy" />
      ) : icon ? (
        <span className="compact-line__icon" aria-hidden="true">
          <Icon name={icon} size={16} />
        </span>
      ) : null}
      <span className="compact-line__text">
        <strong>{title}</strong>
        {detail ? <small>{detail}</small> : null}
      </span>
    </>
  );
  return (
    <div className="compact-line">
      {to ? (
        <Link className="compact-line__main" to={to}>
          {body}
        </Link>
      ) : (
        <span className="compact-line__main">{body}</span>
      )}
      {end ? <span className="compact-line__end">{end}</span> : null}
    </div>
  );
}

/** 027 (#36): posters on a single row — a strip swiped sideways (or slowly running when ``running``). */
export function PosterStrip({
  cards,
  running = false,
}: {
  cards: Array<{ key: string; title: string; src: string | null; to?: string | null }>;
  running?: boolean;
}) {
  const shown = running ? [...cards, ...cards] : cards;
  return (
    <div className="poster-strip" data-running={running || undefined}>
      <ul data-nofit>
        {shown.map((card, index) => {
          const art = card.src ? (
            <img src={card.src} alt="" loading="lazy" />
          ) : (
            <span className="poster-strip__title">{card.title}</span>
          );
          return (
            <li
              // biome-ignore lint/suspicious/noArrayIndexKey: a running strip repeats itself
              key={`${card.key}-${index}`}
              title={card.title}
              aria-hidden={index >= cards.length || undefined}
            >
              {card.to ? (
                <Link to={card.to} tabIndex={index >= cards.length ? -1 : undefined} aria-label={card.title}>
                  {art}
                </Link>
              ) : (
                art
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
