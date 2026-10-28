import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { imageUrl } from "../api";
import { Poster } from "../MediaGrid";
import { type TasteCard, useJudge, type Verdict } from "./api";
import { reasonOf } from "./reason";
import { VERDICTS } from "./TasteButtons";
import "./taste.css";

const THROW = 110; // pixels a card is dragged to be judged on release
const LEAVE_MS = 260;

async function more(limit: number): Promise<TasteCard[]> {
  return (await api.GET("/api/v1/me/media/taste/deck", { params: { query: { limit } } })).data?.items ?? [];
}

/**
 * Issue 190: one title at a time to judge — swiped right « I like it », left « not for me », or answered
 * with the four buttons (and the arrow keys): like, not for me, seen, later. The next cards are asked for as
 * the last ones go; the last answer can be taken back.
 */
export function TasteDeck({ initial, limit = 12 }: { initial?: TasteCard[] | undefined; limit?: number }) {
  const t = useT();
  const format = useFormat();
  const judge = useJudge();
  const [queue, setQueue] = useState<TasteCard[]>(initial ?? []);
  const [loading, setLoading] = useState(!initial?.length);
  const [drag, setDrag] = useState<number | null>(null);
  const [leaving, setLeaving] = useState<Verdict | null>(null);
  const [last, setLast] = useState<TasteCard | null>(null);
  const answered = useRef(new Set<string>());
  const start = useRef(0);

  const asking = useRef(false);
  const refill = useCallback(async () => {
    if (asking.current) return; // one call at a time, however fast the cards go
    asking.current = true;
    setLoading(true);
    try {
      const fresh = (await more(limit)).filter((card) => !answered.current.has(card.id));
      setQueue((current) => [...current, ...fresh.filter((card) => !current.some((c) => c.id === card.id))]);
    } finally {
      asking.current = false;
      setLoading(false);
    }
  }, [limit]);

  // the first cards: the block's own, or asked for once
  const started = useRef(Boolean(initial?.length));
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void refill();
  }, [refill]);

  const card = queue[0];
  const answer = (verdict: Verdict) => {
    if (!card || leaving) return;
    answered.current.add(card.id);
    judge.mutate({ objectId: card.id, verdict });
    setLeaving(verdict);
    setLast(card);
    window.setTimeout(() => {
      setQueue((current) => current.slice(1));
      setLeaving(null);
      setDrag(null);
      if (queue.length <= 3) void refill();
    }, LEAVE_MS);
  };
  const undo = () => {
    if (!last) return;
    judge.mutate({ objectId: last.id, verdict: null });
    answered.current.delete(last.id);
    setQueue((current) => [last, ...current.filter((c) => c.id !== last.id)]);
    setLast(null);
  };

  if (!card) {
    return (
      <div className="taste-deck">
        <p className="widget-empty">
          {loading ? t("media:taste.deck.loading") : t("media:taste.deck.empty")}
        </p>
        {loading ? null : (
          <button type="button" className="media-taste__button" onClick={() => void refill()}>
            <Icon name="shuffle" size={16} />
            <span>{t("media:taste.deck.again")}</span>
          </button>
        )}
      </div>
    );
  }
  const why = reasonOf(card.reason, t, format.list);
  const dx = leaving === "like" ? 600 : leaving === "dislike" ? -600 : (drag ?? 0);
  const facts = [
    t(`media:kind.${card.kind}`),
    card.year ? String(card.year) : null,
    card.rating ? `★ ${format.number(Math.round(card.rating * 10) / 10)}` : null,
    card.genres?.[0] ?? null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: the arrow keys answer as the buttons below do
    <div
      className="taste-deck"
      onKeyDown={(event) => {
        if (event.key === "ArrowRight") answer("like");
        else if (event.key === "ArrowLeft") answer("dislike");
      }}
    >
      <div className="taste-deck__stage">
        {queue[1] ? <span className="taste-deck__next" aria-hidden="true" /> : null}
        <article
          className="taste-deck__card"
          aria-label={card.title}
          data-dragging={drag !== null && !leaving ? "" : undefined}
          data-leaving={leaving ? "" : undefined}
          style={{
            transform: `translateX(${dx}px) rotate(${dx / 24}deg)`,
            ["--hint" as string]: String(Math.min(1, Math.abs(drag ?? 0) / THROW)),
          }}
          onPointerDown={(event) => {
            if ((event.target as HTMLElement).closest("a")) return;
            start.current = event.clientX;
            setDrag(0);
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (drag !== null && !leaving) setDrag(event.clientX - start.current);
          }}
          onPointerUp={() => {
            if (drag === null) return;
            if (drag > THROW) answer("like");
            else if (drag < -THROW) answer("dislike");
            else setDrag(null);
          }}
          onPointerCancel={() => setDrag(null)}
        >
          <span className="taste-deck__poster">
            <Poster src={imageUrl(card.image_id)} kind={card.kind} />
          </span>
          <div className="taste-deck__text">
            <h3 className="taste-deck__title">
              <Link to={`/media/${card.id}`}>{card.title}</Link>
            </h3>
            <span className="taste-deck__facts">{facts}</span>
            {card.seen ? (
              <span className="taste-deck__seen">{t("media:taste.deck.seen")}</span>
            ) : why ? (
              <span className="media-card__reason" title={why.like ?? undefined}>
                <Icon name="sparkles" size={12} />
                <span>{why.short}</span>
              </span>
            ) : null}
            {card.overview ? <p className="taste-deck__overview">{card.overview}</p> : null}
          </div>
          <span
            className="taste-deck__hint"
            data-side="like"
            style={{ opacity: (drag ?? 0) > 0 ? undefined : 0 }}
          >
            {t("media:taste.verdict.like")}
          </span>
          <span
            className="taste-deck__hint"
            data-side="dislike"
            style={{ opacity: (drag ?? 0) < 0 ? undefined : 0 }}
          >
            {t("media:taste.verdict.dislike")}
          </span>
        </article>
      </div>
      <fieldset className="taste-deck__answers" aria-label={t("media:taste.about", { title: card.title })}>
        {VERDICTS.map(({ verdict, icon }) => (
          <button
            key={verdict}
            type="button"
            className="media-taste__button"
            data-verdict={verdict}
            onClick={() => answer(verdict)}
            title={t(`media:taste.verdict.${verdict}`)}
          >
            <Icon name={icon} size={16} />
            <span>
              {t(
                card.seen && verdict === "seen" ? "media:taste.deck.skip" : `media:taste.verdict.${verdict}`,
              )}
            </span>
          </button>
        ))}
      </fieldset>
      {last ? (
        <button type="button" className="media-row__more taste-deck__undo" onClick={undo}>
          <Icon name="undo" size={14} />
          {t("media:taste.deck.undo", { title: last.title })}
        </button>
      ) : null}
    </div>
  );
}
