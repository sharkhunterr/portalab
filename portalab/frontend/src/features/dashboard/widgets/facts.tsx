import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";

/**
 * 027: what a card says of its title — its kind (film, series, book, game…), year and genres on one line,
 * its rating, and its overview (cut to what the block can hold). Shared by the card deck and « next
 * releases »; each part shows only when known.
 */
export interface Facts {
  kind?: string | null | undefined;
  year?: number | null | undefined;
  genres?: string[] | null | undefined;
  rating?: number | null | undefined;
  overview?: string | null | undefined;
}

const KINDS = new Set(["movie", "series", "book", "audiobook", "game", "album", "track"]);

export function TitleFacts({ facts, extra }: { facts: Facts; extra?: string | null | undefined }) {
  const t = useT();
  const format = useFormat();
  const kind = facts.kind === "episode" ? "series" : facts.kind;
  const line = [
    kind && KINDS.has(kind) ? t(`media:kind.${kind}`) : null,
    facts.year ? String(facts.year) : null,
    ...(facts.genres ?? []).slice(0, 3),
  ].filter(Boolean);
  return (
    <span className="title-facts">
      {line.length || facts.rating ? (
        <span className="title-facts__line">
          {facts.rating ? (
            <span className="title-facts__rating" title={t("media:facts.rating")}>
              <Icon name="star" size={12} />
              {format.number(facts.rating)}
            </span>
          ) : null}
          {line.length ? <span>{line.join(" · ")}</span> : null}
        </span>
      ) : null}
      {extra ? <small className="title-facts__extra">{extra}</small> : null}
      {facts.overview ? <span className="title-facts__overview">{facts.overview}</span> : null}
    </span>
  );
}
