import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { sound } from "../../../design-system/sound/SoundService";
import { useTheme } from "../../../design-system/themes/ThemeProvider";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { ProductArt } from "../catalog/ProductArt";
import { type Booster, type BoosterCard, localized, useReveal } from "./api";
import { BoosterPack } from "./BoosterShelf";

type Phase = "sealed" | "opening" | "spread" | "done";
const RANK: Record<string, number> = { common: 0, rare: 1, epic: 2, legendary: 3 };
const OPENING_MS = 1300;
const SPOTLIGHT_MS = 2300;

/** A burst of sparks flying out of a point — more and wider the rarer the card. */
function Burst({ count, spread, seed }: { count: number; spread: number; seed: number }) {
  const sparks = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const r = (n: number) => {
          const x = Math.sin((seed + 1) * 9301 + i * 49297 + n * 233) * 43758.5453;
          return x - Math.floor(x);
        };
        return {
          "--angle": `${(360 / count) * i + r(1) * 24}deg`,
          "--distance": `${spread * (0.55 + r(2) * 0.6)}px`,
          "--delay": `${r(3) * 120}ms`,
          "--size": `${4 + r(4) * 7}px`,
          "--hue": i % 3,
        } as CSSProperties;
      }),
    [count, spread, seed],
  );
  return (
    <span className="booster-burst" aria-hidden="true">
      {sparks.map((style, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: sparks of one burst, fixed for its life
        <span key={i} style={style} />
      ))}
    </span>
  );
}

function Card({
  card,
  index,
  flipped,
  spotlight,
  onFlip,
}: {
  card: BoosterCard;
  index: number;
  flipped: boolean;
  spotlight: boolean;
  onFlip: () => void;
}) {
  const t = useT();
  const format = useFormat();
  const rarity = card.product.rarity ?? "common";
  const rank = RANK[rarity] ?? 0;
  const label = flipped
    ? `${card.product.name} — ${t(`marketplace:rarity.${rarity}`)}${card.duplicate ? ` — ${t("marketplace:booster.duplicate")}` : ""}`
    : t("marketplace:booster.hidden", { n: index + 1 });
  return (
    <li
      className="booster-card"
      data-rarity={rarity}
      data-flipped={flipped || undefined}
      data-spotlight={spotlight || undefined}
      data-duplicate={card.duplicate || undefined}
      style={{ "--i": index } as CSSProperties}
    >
      <button
        type="button"
        className="booster-card__button"
        onClick={onFlip}
        disabled={flipped}
        aria-label={label}
      >
        <span className="booster-card__inner">
          <span className="booster-card__back" aria-hidden="true">
            <span className="booster-card__back-pattern" />
            <Icon name="sparkles" size={28} />
          </span>
          <span className="booster-card__face" aria-hidden="true">
            <span className="booster-card__shine" />
            <span className="booster-card__art">
              <ProductArt product={card.product} size="card" />
            </span>
            <span className="booster-card__rarity">{t(`marketplace:rarity.${rarity}`)}</span>
            <strong className="booster-card__name">{card.product.name}</strong>
            <span className="booster-card__type">{t(`marketplace:type.${card.product.type}`)}</span>
            {card.duplicate ? (
              <span className="booster-card__stamp">{t("marketplace:booster.duplicate")}</span>
            ) : (
              <span className="booster-card__new">{t("marketplace:booster.new")}</span>
            )}
          </span>
        </span>
      </button>
      {flipped && rank >= 1 ? (
        <Burst count={rank === 3 ? 42 : rank === 2 ? 26 : 14} spread={60 + rank * 45} seed={index} />
      ) : null}
      {flipped && card.duplicate ? (
        <span className="booster-card__refund" aria-hidden="true">
          <Icon name="coins" size={14} />+{format.number(card.refund)}
        </span>
      ) : null}
    </li>
  );
}

/**
 * #81 (proof of concept): opening a booster — the sealed pack floats; a tap shakes it, it tears open in a
 * flash and its cards are dealt face down, the rarer ones already glowing through. Each turns on a tap (or
 * all, one after another): a rare one glints, an epic one bursts, a legendary one takes the stage — the
 * screen dims, golden rays turn behind it. A card already owned gets a « duplicate » stamp and the Coins it
 * would give back. A summary closes it. Visual only: nothing is charged, granted or refunded yet.
 */
export function BoosterReveal({ booster, onClose }: { booster: Booster; onClose: () => void }) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const reduced = useTheme().effective.reducedMotion;
  const reveal = useReveal();
  const [phase, setPhase] = useState<Phase>("sealed");
  const [flipped, setFlipped] = useState<ReadonlySet<number>>(new Set());
  const [spotlight, setSpotlight] = useState<number | null>(null);
  const timers = useRef<number[]>([]);
  const dialog = useRef<HTMLDivElement>(null);
  const cards = reveal.data?.cards ?? [];
  const later = useCallback((fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms));
  }, []);

  const draw = useCallback(() => {
    reveal.reset();
    setFlipped(new Set());
    setSpotlight(null);
    setPhase("sealed");
    reveal.mutate(booster.key);
  }, [booster.key, reveal]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: draw once when it opens
  useEffect(() => {
    draw();
    dialog.current?.focus();
    const keep = timers.current;
    return () => {
      for (const id of keep) window.clearTimeout(id);
    };
  }, []);

  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const open = () => {
    if (phase !== "sealed" || !reveal.data) return;
    void sound.play("ui");
    if (reduced) {
      setPhase("spread");
      return;
    }
    setPhase("opening");
    later(() => setPhase("spread"), OPENING_MS);
  };

  const flip = useCallback(
    (index: number) => {
      const card = cards[index];
      if (!card) return;
      setFlipped((current) => new Set(current).add(index));
      const rank = RANK[card.product.rarity ?? "common"] ?? 0;
      void sound.play(rank >= 2 ? "reward" : rank === 1 ? "success" : "ui");
      if (rank === 3 && !reduced) {
        setSpotlight(index);
        later(() => setSpotlight((now) => (now === index ? null : now)), SPOTLIGHT_MS);
      }
    },
    [cards, later, reduced],
  );

  const revealAll = () => {
    let wait = 0;
    cards.forEach((card, index) => {
      if (flipped.has(index)) return;
      later(() => flip(index), wait);
      wait += (RANK[card.product.rarity ?? "common"] ?? 0) === 3 && !reduced ? SPOTLIGHT_MS + 200 : 520;
    });
  };

  const all = cards.length > 0 && flipped.size === cards.length;
  useEffect(() => {
    if (all && phase === "spread") later(() => setPhase("done"), reduced ? 0 : 1100);
  }, [all, phase, later, reduced]);

  const refund = cards.reduce((sum, card) => sum + (card.duplicate ? card.refund : 0), 0);
  const best = cards.reduce((top, card) => Math.max(top, RANK[card.product.rarity ?? "common"] ?? 0), 0);
  const name = localized(booster.names, locale);

  return createPortal(
    <div
      ref={dialog}
      className="booster-stage"
      role="dialog"
      aria-modal="true"
      aria-label={t("marketplace:booster.opening", { name })}
      tabIndex={-1}
      data-phase={phase}
      data-spotlight={spotlight !== null || undefined}
      // the stage takes the best card's colour only once every card is turned (no spoiler)
      data-best={phase === "done" ? ["common", "rare", "epic", "legendary"][best] : undefined}
      data-reduced={reduced || undefined}
    >
      <span className="booster-stage__rays" aria-hidden="true" />
      <button
        type="button"
        className="booster-stage__close"
        onClick={onClose}
        aria-label={t("marketplace:booster.close")}
      >
        <Icon name="close" size={20} />
      </button>
      <p className="booster-stage__preview">
        <Icon name="eye" size={14} />
        {t("marketplace:booster.previewNote")}
      </p>

      {phase === "sealed" || phase === "opening" ? (
        <div className="booster-stage__pack">
          <button
            type="button"
            className="booster-stage__tear"
            onClick={open}
            disabled={!reveal.data || phase === "opening"}
            aria-label={t("marketplace:booster.tear", { name })}
          >
            <BoosterPack booster={booster} stage />
            {phase === "opening" ? <span className="booster-stage__flash" aria-hidden="true" /> : null}
          </button>
          <p className="booster-stage__hint" aria-live="polite">
            {reveal.isError
              ? t("marketplace:booster.failed")
              : reveal.data
                ? phase === "opening"
                  ? t("marketplace:booster.tearing")
                  : t("marketplace:booster.tapToOpen")
                : t("marketplace:booster.sealing")}
          </p>
        </div>
      ) : (
        <>
          <ul className="booster-cards" aria-label={name}>
            {cards.map((card, index) => (
              <Card
                key={card.product.key}
                card={card}
                index={index}
                flipped={flipped.has(index)}
                spotlight={spotlight === index}
                onFlip={() => flip(index)}
              />
            ))}
          </ul>
          {phase === "spread" && !all ? (
            <div className="booster-stage__actions">
              <p className="booster-stage__hint">{t("marketplace:booster.tapCards")}</p>
              <Button variant="secondary" onClick={revealAll}>
                <Icon name="sparkles" size={16} />
                {t("marketplace:booster.revealAll")}
              </Button>
            </div>
          ) : null}
          {phase === "done" ? (
            <section className="booster-summary" aria-label={t("marketplace:booster.summary")}>
              <h2>{t(`marketplace:booster.verdict.${["common", "rare", "epic", "legendary"][best]}`)}</h2>
              <ul className="booster-summary__list">
                {cards.map((card) => (
                  <li key={card.product.key} data-rarity={card.product.rarity ?? "common"}>
                    <span className="booster-summary__dot" />
                    <span className="booster-summary__name">{card.product.name}</span>
                    <span className="booster-summary__state">
                      {card.duplicate
                        ? t("marketplace:booster.refundLine", { coins: format.number(card.refund) })
                        : t("marketplace:booster.new")}
                    </span>
                  </li>
                ))}
              </ul>
              {refund ? (
                <p className="booster-summary__refund">
                  <Icon name="coins" size={16} />
                  {t("marketplace:booster.refundTotal", { coins: format.number(refund) })}
                </p>
              ) : null}
              <p className="booster-summary__note">{t("marketplace:booster.notYet")}</p>
              <div className="booster-summary__actions">
                <Button variant="secondary" onClick={onClose}>
                  {t("marketplace:booster.close")}
                </Button>
                <Button onClick={draw}>
                  <Icon name="sparkles" size={16} />
                  {t("marketplace:booster.again")}
                </Button>
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>,
    document.body,
  );
}
