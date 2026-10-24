import { type CSSProperties, useEffect, useState } from "react";
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
const TURN = 3500; // how long a card stays in front (ms)

/** How far a card is from the one in front, the hand going round: in (-size/2, size/2]. */
function offset(index: number, front: number, size: number): number {
  const d = (((index - front) % size) + size) % size;
  return d > size / 2 ? d - size : d;
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
  const [front, setFront] = useState<number | null>(null);
  const [held, setHeld] = useState(false);
  // the hand opens on the first card I own
  const shown =
    front ??
    Math.max(
      0,
      cards.findIndex((card) => best(card)),
    );
  useEffect(() => {
    if (reduced || held || size < 2) return;
    const timer = window.setTimeout(() => setFront((shown + 1) % size), TURN);
    return () => window.clearTimeout(timer);
  }, [reduced, held, size, shown]);
  const data = set.data;
  if (!data || !size) return null;
  const owned = cards.filter((card) => best(card));
  const held_copies = cards.reduce((sum, card) => sum + copies(card), 0);
  const foils = cards.filter((card) =>
    Object.entries(card.owned).some(([v, n]) => v.endsWith("foil") && n),
  ).length;
  const percent = Math.round((data.owned / (data.size || 1)) * 100);
  const turn = (by: number) => setFront((shown + by + size) % size);
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
        <ul aria-label={t("gamification:cards.work.hand", { code: data.code })}>
          {cards.map((card, index) => {
            const d = offset(index, shown, size);
            return (
              // a card aside comes to the front when tapped; only the one in front opens
              <li
                key={card.id}
                data-front={d === 0 || undefined}
                data-away={Math.abs(d) > REACH || undefined}
                aria-hidden={d !== 0 || undefined}
                style={{ "--d": d, "--far": Math.abs(d), zIndex: 20 - Math.abs(d) } as CSSProperties}
                onClick={d === 0 ? undefined : () => setFront(index)}
              >
                <div inert={d !== 0 || undefined}>
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
              onClick={() => turn(-1)}
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
              onClick={() => turn(1)}
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
