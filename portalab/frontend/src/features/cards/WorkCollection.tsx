import { type CSSProperties, type PointerEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import { useT } from "../../i18n/hooks/useT";
import { type MediaCard, type Rarity, useCardSet } from "./api";
import { best, CardSheet } from "./SetPage";
import "./cards.css";

const RARITIES: Rarity[] = ["common", "rare", "epic", "legendary"];
const REACH = 3; // the cards fanned out on each side of the one in front
const TURN = 3500; // how long a card stays in front when the hand is left alone (ms)
const STEP = 0.26; // a card's step in the fan, as a share of its width (the stylesheet's ``--hand-step``)
const FLING = 260; // how far a swipe carries on: its speed (cards per ms) times this
const TAP = 6; // a move shorter than this (px) is a tap, not a swipe

/** How far a card is from the place in front, the hand going round: in (-size/2, size/2] — fractional while
 * the hand turns. */
function offset(index: number, at: number, size: number): number {
  const d = (((index - at) % size) + size) % size;
  return d > size / 2 ? d - size : d;
}

const ease = (x: number) => 1 - (1 - x) ** 3;

/** The hand's place (which card is in front, fractional while it turns): followed under the finger, carried on
 * by a swipe's speed then settled on a card, turned to the next one when left alone. */
function useHand(size: number, start: number, reduced: boolean) {
  const [at, setAt] = useState(start);
  const place = useRef(start);
  const frame = useRef(0);
  const [moving, setMoving] = useState(false);
  // the set comes after the first draw: the hand then opens on its card
  const ready = useRef(false);
  useEffect(() => {
    if (ready.current || !size) return;
    ready.current = true;
    place.current = start;
    setAt(start);
  }, [size, start]);
  const go = useCallback(
    (to: number, ms: number) => {
      cancelAnimationFrame(frame.current);
      const from = place.current;
      if (reduced || ms <= 0 || from === to) {
        place.current = to;
        setAt(to);
        setMoving(false);
        return;
      }
      setMoving(true);
      const begun = performance.now();
      const tick = (now: number) => {
        const x = Math.min(1, (now - begun) / ms);
        place.current = from + (to - from) * ease(x);
        setAt(place.current);
        if (x < 1) frame.current = requestAnimationFrame(tick);
        else setMoving(false);
      };
      frame.current = requestAnimationFrame(tick);
    },
    [reduced],
  );
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  // to a card, the shortest way round
  const toCard = useCallback(
    (index: number) => {
      const to = Math.round(place.current + offset(index, place.current, size));
      go(to, 380 + Math.abs(to - place.current) * 90);
    },
    [go, size],
  );
  const by = useCallback(
    (cards: number) => {
      const to = Math.round(place.current) + cards;
      go(to, 380 + Math.abs(to - place.current) * 90);
    },
    [go],
  );
  // a swipe: the hand follows the finger, then goes on at its speed and settles on a card
  const drag = useRef<{
    x: number;
    from: number;
    px: number;
    moved: boolean;
    trail: [number, number][];
  } | null>(null);
  const [dragging, setDragging] = useState(false);
  const down = (event: PointerEvent<HTMLElement>) => {
    if (size < 2 || (event.pointerType === "mouse" && event.button !== 0)) return;
    cancelAnimationFrame(frame.current);
    setMoving(false);
    const card = event.currentTarget.querySelector("li");
    drag.current = {
      x: event.clientX,
      from: place.current,
      px: Math.max(1, (card?.getBoundingClientRect().width ?? 200) * STEP),
      moved: false,
      trail: [[event.timeStamp, event.clientX]],
    };
  };
  const move = (event: PointerEvent<HTMLElement>) => {
    const now = drag.current;
    if (!now) return;
    const dx = event.clientX - now.x;
    if (!now.moved && Math.abs(dx) < TAP) return;
    if (!now.moved) {
      now.moved = true;
      setDragging(true);
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    now.trail = [
      ...now.trail.filter(([time]) => event.timeStamp - time < 120),
      [event.timeStamp, event.clientX],
    ];
    place.current = now.from - dx / now.px;
    setAt(place.current);
  };
  const up = (event: PointerEvent<HTMLElement>) => {
    const now = drag.current;
    drag.current = null;
    if (!now?.moved) return;
    setDragging(false);
    const [first] = now.trail;
    const elapsed = first ? event.timeStamp - first[0] : 0;
    const speed = first && elapsed > 0 ? -(event.clientX - first[1]) / now.px / elapsed : 0; // cards per ms
    const carried = Math.max(-size, Math.min(size, speed * FLING));
    const to = Math.round(place.current + carried);
    go(to, Math.min(1200, 320 + Math.abs(to - place.current) * 110));
    // the click that ends a swipe opens nothing
    const swallow = (click: Event) => {
      click.stopPropagation();
      click.preventDefault();
    };
    window.addEventListener("click", swallow, { capture: true, once: true });
    window.setTimeout(() => window.removeEventListener("click", swallow, { capture: true }), 350);
  };
  return {
    at,
    moving,
    dragging,
    go,
    toCard,
    by,
    swipe: { onPointerDown: down, onPointerMove: move, onPointerUp: up, onPointerCancel: up },
  };
}

const copies = (card: MediaCard) => Object.values(card.owned).reduce((a, b) => a + (b ?? 0), 0);

/** Issue 234: a work's collection on its own page, as a hand of cards — fanned out, turning one at a time
 * (those I own in colour, the others dimmed), a tap opens one; beside it what the set holds and what I have
 * of it, and the way to the whole collection. Nothing when the work has none. */
export function WorkCollection({ objectId }: { objectId: string }) {
  const t = useT();
  const set = useCardSet(objectId, { quiet: true });
  const reduced = useTheme().effective.reducedMotion;
  const cards = set.data?.cards ?? [];
  const size = cards.length;
  const [held, setHeld] = useState(false);
  // the hand opens on the first card I own
  const start = Math.max(
    0,
    cards.findIndex((card) => best(card)),
  );
  const hand = useHand(size, start, reduced);
  const shown = ((Math.round(hand.at) % size) + size) % size || 0;
  // left alone, it turns to the next card
  const busy = held || hand.moving || hand.dragging;
  const { by } = hand;
  useEffect(() => {
    if (reduced || busy || size < 2) return;
    const timer = window.setTimeout(() => by(1), TURN);
    return () => window.clearTimeout(timer);
  }, [reduced, busy, size, by]);
  const data = set.data;
  if (!data || !size) return null;
  const owned = cards.filter((card) => best(card));
  const held_copies = cards.reduce((sum, card) => sum + copies(card), 0);
  const foils = cards.filter((card) =>
    Object.entries(card.owned).some(([v, n]) => v.endsWith("foil") && n),
  ).length;
  const percent = Math.round((data.owned / (data.size || 1)) * 100);
  return (
    <section className="cards-work" aria-labelledby="cards-work-title">
      {/* biome-ignore lint/a11y/noStaticElementInteractions: the hand stops turning while pointed at or focused */}
      <div
        className="cards-hand"
        onPointerEnter={() => setHeld(true)}
        onPointerLeave={() => setHeld(false)}
        onFocus={() => setHeld(true)}
        onBlur={() => setHeld(false)}
      >
        <ul
          aria-label={t("gamification:cards.work.hand", { code: data.code })}
          data-dragging={hand.dragging || undefined}
          {...hand.swipe}
        >
          {cards.map((card, index) => {
            const d = offset(index, hand.at, size);
            const far = Math.abs(d);
            const front = far < 0.5;
            return (
              // a card aside comes to the front when tapped; only the one in front opens
              <li
                key={card.id}
                data-front={front || undefined}
                data-away={far > REACH + 0.5 || undefined}
                aria-hidden={!front || undefined}
                style={
                  {
                    "--d": d,
                    "--far": far,
                    opacity: Math.max(0, Math.min(1, REACH + 1 - far)),
                    zIndex: Math.round(100 - far * 10),
                  } as CSSProperties
                }
                onClick={front ? undefined : () => hand.toCard(index)}
              >
                <div inert={!front || undefined}>
                  <CardSheet card={card} />
                </div>
              </li>
            );
          })}
        </ul>
        {size > 1 ? (
          <div className="cards-hand__turn">
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("gamification:cards.work.previous")}
              onClick={() => hand.by(-1)}
            >
              <Icon name="chevron-left" size={18} />
            </Button>
            <span aria-live="polite">
              {shown + 1} / {size}
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("gamification:cards.work.next")}
              onClick={() => hand.by(1)}
            >
              <Icon name="chevron-right" size={18} />
            </Button>
          </div>
        ) : null}
      </div>
      <div className="cards-work__facts">
        <h2 id="cards-work-title">
          <Icon name="layers" size={18} /> {t("gamification:cards.work.title")}
        </h2>
        <p className="cards-work__set">
          {t("gamification:cards.setLine", { code: data.code, owned: data.owned, size: data.size })}
        </p>
        <div className="cards-work__progress">
          <strong>{t("gamification:cards.work.percent", { percent })}</strong>
          <span>{t("gamification:cards.work.owned", { owned: data.owned, size: data.size })}</span>
          <progress max={data.size || 1} value={data.owned} aria-hidden="true" />
        </div>
        <h3>{t("gamification:cards.work.rarities")}</h3>
        <dl className="cards-work__rarities">
          {RARITIES.map((rarity) => {
            const all = cards.filter((card) => card.rarity === rarity);
            if (!all.length) return null;
            return (
              <div key={rarity} data-rarity={rarity}>
                <dt>{t(`gamification:cards.rarity.${rarity}`)}</dt>
                <dd>
                  {owned.filter((card) => card.rarity === rarity).length} / {all.length}
                </dd>
              </div>
            );
          })}
        </dl>
        <p className="cards-work__copies">
          {t("gamification:cards.work.copies", { count: held_copies })} ·{" "}
          {t("gamification:cards.work.doubles", { count: held_copies - owned.length })} ·{" "}
          {t("gamification:cards.work.foils", { count: foils })}
        </p>
        <Button asChild variant="secondary">
          <Link to={`/cards/sets/${data.key}`}>
            <Icon name="layers" size={16} /> {t("gamification:cards.work.open")}
          </Link>
        </Button>
      </div>
    </section>
  );
}
