import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FxLayer } from "../../../design-system/components/Fx";
import { Icon } from "../../../design-system/components/Icon";
import { sound } from "../../../design-system/sound/SoundService";
import { useTheme } from "../../../design-system/themes/ThemeProvider";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { useProgression } from "../../gamification/api";
import { ProductArt } from "../catalog/ProductArt";
import { type Booster, type BoosterCard, localized, requestKey, useOpenBooster } from "./api";
import { BoosterPack, useCanOpen } from "./Boosters";
import { hookOf, type Rarity, type Scene, ScenePart, useBoosterScene } from "./scene/scene";

type Phase = "sealed" | "tearing" | "emerging" | "spread" | "done";
type CardState = "hidden" | "charging" | "revealed";
const RARITIES = ["common", "rare", "epic", "legendary"] as const;
const RANK: Record<string, number> = { common: 0, rare: 1, epic: 2, legendary: 3 };
// how long each rarity builds up before its card turns (the rarer, the longer the suspense)
const CHARGE_MS = [180, 700, 1250, 2100];
// how long its moment lasts once turned
const AFTER_MS = [450, 800, 1100, 1700];
const TEAR_MS = 1500;
// the GPU's bursts around a card per rarity (none for a common one; a legendary has the whole stage)
const GPU_BURST = ["", "burst:voltage", "burst:plasma", ""];
const EMERGE_MS = 1100;
// the fractures on the back of an epic or legendary card (in a 100 × 140 box), main lines then branches
const CRACKS = [
  "M50 70 L43 61 L46 52 L37 41 L40 30 L31 18 L33 6",
  "M43 61 L33 60 L25 54",
  "M50 70 L59 64 L63 55 L74 49 L79 38 L91 31",
  "M63 55 L60 44 L66 36",
  "M50 70 L56 81 L52 91 L60 102 L57 114 L65 131",
  "M52 91 L42 97 L36 108",
  "M50 70 L39 76 L30 74 L20 83 L9 85",
  "M60 102 L71 106 L77 117",
];

/** A deterministic pseudo-random sequence: the same layout on every render. */
function noise(seed: number, n: number): number {
  const x = Math.sin(seed * 9301 + n * 49297 + 233) * 43758.5453;
  return x - Math.floor(x);
}

/** Sparks flying out of a point — more, wider and longer the rarer the card. */
function Burst({ rank, seed }: { rank: number; seed: number }) {
  const count = [10, 18, 30, 54][rank] ?? 10;
  const spread = [70, 110, 170, 260][rank] ?? 70;
  const sparks = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        "--angle": `${(360 / count) * i + noise(seed + i, 1) * 20}deg`,
        "--distance": `${spread * (0.5 + noise(seed + i, 2) * 0.7)}px`,
        "--delay": `${noise(seed + i, 3) * 140}ms`,
        "--size": `${3 + noise(seed + i, 4) * (4 + rank * 2)}px`,
      })) as CSSProperties[],
    [count, spread, seed, rank],
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

/** The mist the stage stands in: clouds drifting, dust rising, projectors sweeping it from above. */
function Atmosphere() {
  const dust = useMemo(
    () =>
      Array.from({ length: 34 }, (_, i) => ({
        "--x": `${noise(i, 1) * 100}%`,
        "--delay": `${-noise(i, 2) * 14}s`,
        "--duration": `${9 + noise(i, 3) * 10}s`,
        "--size": `${1 + noise(i, 4) * 3}px`,
        "--drift": `${(noise(i, 5) - 0.5) * 120}px`,
      })) as CSSProperties[],
    [],
  );
  return (
    <span className="booster-atmosphere" aria-hidden="true">
      {/* HD: the fog and the projectors drawn by the GPU; the CSS ones below stay where it cannot draw */}
      <span className="booster-atmosphere__gpu">
        <FxLayer effect="mist" maxSide={900} className="booster-stage__gpu-canvas" />
      </span>
      <span className="booster-atmosphere__beam" data-beam="1" />
      <span className="booster-atmosphere__beam" data-beam="2" />
      <span className="booster-atmosphere__beam" data-beam="3" />
      <span className="booster-atmosphere__fog" data-layer="1" />
      <span className="booster-atmosphere__fog" data-layer="2" />
      <span className="booster-atmosphere__fog" data-layer="3" />
      <span className="booster-atmosphere__dust">
        {dust.map((style, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: dust motes, fixed
          <span key={i} style={style} />
        ))}
      </span>
      <span className="booster-atmosphere__glow" />
      <span className="booster-atmosphere__vignette" />
    </span>
  );
}

function Card({
  card,
  index,
  total,
  state,
  onReveal,
  scene,
  reduced = false,
}: {
  card: BoosterCard;
  index: number;
  total: number;
  state: CardState;
  onReveal: () => void;
  /** 028: a pack's scene — its faces, backs and reveal effects per rarity (Portalab's own where it brings none) */
  scene?: Scene | null;
  reduced?: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const rarity = card.product.rarity ?? "common";
  const rank = RANK[rarity] ?? 0;
  const parts = scene?.parts;
  // face down, its back tells nothing: the « common » back until it starts turning
  const back = parts?.back?.[(state === "hidden" ? "common" : rarity) as Rarity] ?? parts?.back?.common;
  const face = parts?.face?.[rarity as Rarity] ?? parts?.face?.common;
  const reveal = parts?.reveal?.[rarity as Rarity];
  const label =
    state === "revealed"
      ? `${card.product.name} — ${t(`marketplace:rarity.${rarity}`)} — ${t(
          card.outcome === "duplicate"
            ? "marketplace:booster.duplicate"
            : card.outcome === "reserve"
              ? "marketplace:booster.reserveCard"
              : "marketplace:booster.new",
        )}`
      : t("marketplace:booster.hidden", { n: index + 1 });
  return (
    <li
      className="booster-card"
      // face down, nothing tells its rarity — not even in the page
      data-rarity={state === "hidden" ? undefined : rarity}
      data-state={state}
      data-duplicate={(state === "revealed" && card.duplicate) || undefined}
      data-outcome={state === "revealed" ? card.outcome : undefined}
      data-card-back={hookOf(back)}
      data-card-face={state === "hidden" ? undefined : hookOf(face)}
      data-reveal={state === "revealed" ? hookOf(reveal) : undefined}
      style={{ "--i": index, "--offset": index - (total - 1) / 2 } as CSSProperties}
    >
      {state === "revealed" && reveal ? (
        <ScenePart
          element={reveal}
          className="booster-fx__scene"
          context={{ reducedMotion: reduced, phase: "reveal", rarity, index, count: total }}
        />
      ) : null}
      {!reveal && state !== "hidden" && rank >= 1 ? (
        <span className="booster-fx" aria-hidden="true">
          <span className="booster-fx__ring" />
          {rank >= 2 ? <span className="booster-fx__vortex" /> : null}
          {rank >= 3 ? <span className="booster-fx__halo" /> : null}
        </span>
      ) : null}
      <button
        type="button"
        className="booster-card__button"
        onClick={onReveal}
        disabled={state !== "hidden"}
        aria-label={label}
      >
        <span className="booster-card__inner">
          <span className="booster-card__back" aria-hidden="true">
            <span className="booster-card__back-pattern" />
            <span className="booster-card__back-sigil">
              <Icon name="sparkles" size={30} />
            </span>
            {/* light breaking through: jagged fractures spreading from the middle */}
            <svg
              className="booster-card__cracks"
              viewBox="0 0 100 140"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              {CRACKS.map((d) => (
                <path key={d} d={d} pathLength={1} />
              ))}
            </svg>
          </span>
          <span className="booster-card__face" aria-hidden="true">
            <span className="booster-card__shine" />
            <span className="booster-card__art">
              {/* the card says itself whether it is new or a duplicate */}
              <ProductArt product={{ ...card.product, owned: false }} size="card" />
            </span>
            <span className="booster-card__rarity">{t(`marketplace:rarity.${rarity}`)}</span>
            <strong className="booster-card__name">{card.product.name}</strong>
            <span className="booster-card__type">{t(`marketplace:type.${card.product.type}`)}</span>
            {card.outcome === "duplicate" ? (
              <span className="booster-card__stamp">{t("marketplace:booster.duplicate")}</span>
            ) : card.outcome === "reserve" ? (
              // an item to keep: it goes to the reserve, never a duplicate
              <span className="booster-card__new" data-reserve>
                <Icon name="potion" size={11} />
                {t("marketplace:booster.reserveCard")}
              </span>
            ) : (
              <span className="booster-card__new">{t("marketplace:booster.new")}</span>
            )}
          </span>
        </span>
      </button>
      {!reveal && state === "revealed" && GPU_BURST[rank] ? (
        // HD: electricity around a rare card, plasma around an epic one
        <span className="booster-fx__gpu" aria-hidden="true">
          <FxLayer effect={GPU_BURST[rank] ?? ""} aura className="booster-fx__gpu-canvas" />
        </span>
      ) : null}
      {!reveal && state === "revealed" ? (
        <>
          <span className="booster-fx__wave" aria-hidden="true" />
          {rank >= 2 ? <span className="booster-fx__wave booster-fx__wave--late" aria-hidden="true" /> : null}
          <span className="booster-fx__puff" aria-hidden="true" />
          <Burst rank={rank} seed={index * 7 + 3} />
        </>
      ) : null}
      {state === "revealed" && card.locked ? (
        // won early: held, usable once its level or Contribution is reached
        <span className="booster-card__locked">
          <Icon name="lock" size={12} />
          {card.product.min_level
            ? t("marketplace:card.level", { level: card.product.min_level })
            : t("marketplace:card.contribution", { points: card.product.min_contribution ?? 0 })}
        </span>
      ) : null}
      {state === "revealed" && card.duplicate ? (
        <span className="booster-card__refund" aria-hidden="true">
          <Icon name="coins" size={14} />+{format.number(card.refund)}
        </span>
      ) : null}
    </li>
  );
}

/**
 * #81: opening a booster, in the mist — the sealed pack floats under projectors sweeping
 * the haze; a tap and a bright line runs along its top, the strip tears off and flies away, light pours out and the
 * cards rise from it, then line up face down, all alike. Each card turns on a tap (or all, one after
 * another), and its rarity is its moment: a common one turns in a puff of mist; a rare one gathers a blue
 * ring that bursts into a shockwave; an epic one shakes inside a violet vortex and explodes; a legendary
 * one rises to the middle while everything darkens and golden motes spiral into a swelling halo, light
 * cracks through its back — a flash, rings of light, soft rays, embers rising. A card already owned gets a
 * « duplicate » stamp and the Coins it gives back; an item to keep says it goes to the reserve. Tapping the
 * pack opens it for real (its price charged, the looks granted, the duplicates' Coins credited); a summary
 * closes it, with another to open if one can.
 */
export function BoosterReveal({
  booster,
  sealed = false,
  onClose,
}: {
  booster: Booster;
  /** one of the sealed ones I keep (offered, or bought earlier): opened for free */
  sealed?: boolean;
  onClose: () => void;
}) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const reduced = useTheme().effective.reducedMotion;
  const opening = useOpenBooster();
  const scene = useBoosterScene(booster.key); // 028: a pack's scene, Portalab's own otherwise
  // one key per opening: a replayed request is answered without charging twice
  const attempt = useRef(requestKey());
  const coins = useProgression().data?.coins;
  const shown = opening.data?.booster ?? booster;
  const can = useCanOpen(shown);
  // this opening: a sealed one I keep, or one bought now
  const [gift, setGift] = useState(sealed && booster.sealed > 0);
  const ready = gift || can.ok;
  const [phase, setPhase] = useState<Phase>("sealed");
  const [states, setStates] = useState<CardState[]>([]);
  const [moment, setMoment] = useState<string | null>(null);
  const timers = useRef<number[]>([]);
  const dialog = useRef<HTMLDivElement>(null);
  const cards = opening.data?.cards ?? [];
  const later = useCallback((fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms));
  }, []);

  // another one: back to a sealed pack (nothing charged until it is tapped)
  const again = () => {
    for (const id of timers.current) window.clearTimeout(id);
    timers.current = [];
    opening.reset();
    attempt.current = requestKey();
    setGift(shown.sealed > 0);
    setStates([]);
    setMoment(null);
    setPhase("sealed");
  };

  useEffect(() => {
    dialog.current?.focus();
    return () => {
      for (const id of timers.current) window.clearTimeout(id);
    };
  }, []);

  useEffect(() => {
    if (opening.data) setStates(opening.data.cards.map(() => "hidden"));
  }, [opening.data]);

  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const tear = () => {
    void sound.play("ui");
    if (reduced) {
      setPhase("spread");
      return;
    }
    setPhase("tearing");
    // 028: a scene's own opening (a booster inflating then bursting…) takes Portalab's tear's place and time
    const own = scene?.parts.opening;
    const tearMs = own ? Math.min(4000, Math.max(300, (own.duration ?? 1.5) * 1000)) : TEAR_MS;
    later(() => setPhase("emerging"), tearMs);
    later(() => setPhase("spread"), tearMs + (own ? 250 : EMERGE_MS));
  };
  // a tap opens it for real: charged and drawn on the server, then it tears
  const open = () => {
    if (phase !== "sealed" || opening.isPending || !ready) return;
    opening.mutate({ key: booster.key, requestKey: attempt.current, sealed: gift }, { onSuccess: tear });
  };
  const code = String((opening.error as { code?: string } | null)?.code ?? "").replace("marketplace.", "");
  const failure = ["insufficient_coins", "booster_limit", "not_available"].includes(code)
    ? t(`marketplace:booster.error.${code}`)
    : t("marketplace:booster.failed");

  const revealOne = useCallback(
    (index: number) => {
      const card = cards[index];
      if (!card) return;
      const rank = RANK[card.product.rarity ?? "common"] ?? 0;
      const charge = reduced ? 0 : (CHARGE_MS[rank] ?? 0);
      setStates((now) => now.map((s, i) => (i === index && s === "hidden" ? "charging" : s)));
      if (rank >= 2 && !reduced) setMoment(RARITIES[rank] ?? null);
      later(() => {
        setStates((now) => now.map((s, i) => (i === index ? "revealed" : s)));
        void sound.play(rank >= 2 ? "reward" : rank === 1 ? "success" : "ui");
        later(() => setMoment((m) => (m === RARITIES[rank] ? null : m)), AFTER_MS[rank] ?? 400);
      }, charge);
    },
    [cards, later, reduced],
  );

  const revealAll = () => {
    let wait = 0;
    states.forEach((state, index) => {
      if (state !== "hidden") return;
      later(() => revealOne(index), wait);
      const rank = RANK[cards[index]?.product.rarity ?? "common"] ?? 0;
      wait += reduced ? 150 : (CHARGE_MS[rank] ?? 0) + (AFTER_MS[rank] ?? 400) + 150;
    });
  };

  const all = states.length > 0 && states.every((s) => s === "revealed");
  useEffect(() => {
    if (all && phase === "spread") later(() => setPhase("done"), reduced ? 0 : 1400);
  }, [all, phase, later, reduced]);

  const refund = cards.reduce((sum, card) => sum + (card.duplicate ? card.refund : 0), 0);
  const kept = cards.filter((card) => card.outcome === "reserve").length;
  const fresh = cards.filter((card) => card.outcome === "new").length;
  const best = cards.reduce((top, card) => Math.max(top, RANK[card.product.rarity ?? "common"] ?? 0), 0);
  const name = localized(booster.names, locale);
  const busy = states.some((s) => s === "charging");

  return createPortal(
    <div
      ref={dialog}
      className="booster-stage"
      role="dialog"
      aria-modal="true"
      aria-label={t("marketplace:booster.opening", { name })}
      tabIndex={-1}
      data-phase={phase}
      data-moment={moment ?? undefined}
      data-best={phase === "done" ? RARITIES[best] : undefined}
      data-reduced={reduced || undefined}
      data-scene={scene?.look}
      data-own-opening={scene?.parts.opening ? "" : undefined}
    >
      {scene?.parts.backdrop ? (
        // 028: the scene's own animated background in place of the mist, the beams and the glow
        <span className="booster-stage__backdrop" data-booster-backdrop={hookOf(scene.parts.backdrop)}>
          <ScenePart
            element={scene.parts.backdrop}
            className="booster-stage__backdrop-layer"
            context={{ reducedMotion: reduced, phase }}
          />
        </span>
      ) : (
        <Atmosphere />
      )}
      {moment === "legendary" && !scene?.parts.reveal?.legendary ? (
        // HD: the dark closing in, motes drawn to the middle, then a flash, rings, rays and embers as it turns
        <span className="booster-stage__gpu" aria-hidden="true">
          <FxLayer effect="radiance" maxSide={1100} className="booster-stage__gpu-canvas" />
        </span>
      ) : null}
      <button
        type="button"
        className="booster-stage__close"
        onClick={onClose}
        aria-label={t("marketplace:booster.close")}
      >
        <Icon name="close" size={20} />
      </button>
      {coins !== undefined ? (
        <p className="booster-stage__preview">
          <Icon name="coins" size={14} />
          {t("marketplace:booster.balance", { coins: format.number(coins) })}
        </p>
      ) : null}

      {phase === "sealed" || phase === "tearing" || phase === "emerging" ? (
        <div
          className="booster-stage__pack"
          data-booster-look={hookOf(scene?.parts.booster_look)}
          data-opening={phase !== "sealed" ? hookOf(scene?.parts.opening) : undefined}
        >
          <ScenePart
            element={scene?.parts.booster_look}
            className="booster-stage__look"
            context={{ reducedMotion: reduced, phase }}
          />
          {phase !== "sealed" ? (
            <ScenePart
              element={scene?.parts.opening}
              className="booster-stage__opening"
              context={{ reducedMotion: reduced, phase }}
            />
          ) : null}
          <button
            type="button"
            className="booster-stage__tear"
            onClick={open}
            disabled={phase !== "sealed" || opening.isPending || !ready}
            aria-busy={opening.isPending || undefined}
            aria-label={t("marketplace:booster.tear", { name })}
          >
            <BoosterPack booster={booster} stage />
            <span className="booster-stage__tearline" aria-hidden="true" />
            <span className="booster-stage__glow" aria-hidden="true" />
            <span className="booster-stage__rising" aria-hidden="true">
              {cards.map((card, index) => (
                <span key={card.product.key} style={{ "--i": index } as CSSProperties} />
              ))}
            </span>
          </button>
          <p className="booster-stage__hint" aria-live="polite">
            {opening.isError
              ? failure
              : opening.isPending
                ? t("marketplace:booster.sealing")
                : phase !== "sealed"
                  ? t("marketplace:booster.tearing")
                  : gift
                    ? t("marketplace:booster.tapToOpenGift")
                    : can.ok
                      ? t("marketplace:booster.tapToOpen", { price: format.number(booster.price) })
                      : can.reason}
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
                total={cards.length}
                state={states[index] ?? "hidden"}
                scene={scene}
                reduced={reduced}
                onReveal={() => {
                  if (!busy) revealOne(index);
                }}
              />
            ))}
          </ul>
          {phase === "spread" && !all ? (
            <div className="booster-stage__actions">
              <p className="booster-stage__hint">{t("marketplace:booster.tapCards")}</p>
              <Button variant="secondary" onClick={revealAll} disabled={busy}>
                <Icon name="sparkles" size={16} />
                {t("marketplace:booster.revealAll")}
              </Button>
            </div>
          ) : null}
          {phase === "done" ? (
            <section className="booster-summary" aria-label={t("marketplace:booster.summary")}>
              <h2>{t(`marketplace:booster.verdict.${RARITIES[best]}`)}</h2>
              <ul className="booster-summary__list">
                {cards.map((card) => (
                  <li key={card.product.key} data-rarity={card.product.rarity ?? "common"}>
                    <span className="booster-summary__dot" />
                    <span className="booster-summary__name">{card.product.name}</span>
                    <span className="booster-summary__state">
                      {card.outcome === "duplicate"
                        ? t("marketplace:booster.refundLine", { coins: format.number(card.refund) })
                        : card.outcome === "reserve"
                          ? t("marketplace:booster.reserveLine")
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
              <p className="booster-summary__note">
                {[
                  shown.kind === "looks" ? t("marketplace:booster.newTotal", { count: fresh }) : null,
                  kept ? t("marketplace:booster.reserveTotal", { count: kept }) : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <div className="booster-summary__actions">
                <Button variant="secondary" onClick={onClose}>
                  {t("marketplace:booster.close")}
                </Button>
                {kept ? (
                  <Link className="booster-summary__link" to="/marketplace/reserve" onClick={onClose}>
                    <Icon name="potion" size={16} />
                    {t("marketplace:booster.seeReserve")}
                  </Link>
                ) : null}
                <Button
                  onClick={again}
                  disabled={!(shown.sealed > 0 || can.ok)}
                  title={shown.sealed > 0 ? undefined : (can.reason ?? undefined)}
                >
                  <Icon name="sparkles" size={16} />
                  {shown.sealed > 0
                    ? t("marketplace:booster.againGift", { count: shown.sealed })
                    : t("marketplace:booster.again", { price: format.number(shown.price) })}
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
