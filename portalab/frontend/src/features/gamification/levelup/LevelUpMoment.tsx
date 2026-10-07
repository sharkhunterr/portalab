import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { type CSSProperties, useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { LevelBadge } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { sound } from "../../../design-system/sound/SoundService";
import { useTheme } from "../../../design-system/themes/ThemeProvider";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Product } from "../../marketplace/api";
import "../../../design-system/themes/levelup.css";

/**
 * The level-up moment (027): when a level is reached, the screen celebrates it in the member's chosen
 * style (classic rays, arcade, a cosmic black hole, a comic splash page, the four elements, a film
 * premiere) and says what it brought — the new level and its rank, the XP that did it, the level rewards
 * crossed (Coins, Contribution, an offered product), the achievements unlocked with what they gave, and
 * what the shop now offers at this level. It waits to be closed (Escape, the button); under reduced motion
 * nothing moves.
 */
export interface LevelUpEvent {
  level: number;
  from?: number | undefined;
  xp?: number | undefined;
  /** A preview (Appearance, the shop): sample content and this look. */
  preview?: string | undefined;
}

const EVENT = "portalab:level-up";

/** Show the level-up moment (the live progression stream, or a preview). */
export function showLevelUp(event: LevelUpEvent): void {
  window.dispatchEvent(new CustomEvent<LevelUpEvent>(EVENT, { detail: event }));
}

interface Reward {
  value: string;
  amount: number;
}
interface Unlock {
  product: string;
  kind: string;
  label: string;
}
interface Summary {
  level: number;
  previous: number;
  xp: number;
  level_floor: number;
  next_level_at: number | null;
  rewards: Array<{
    level: number;
    coins: number;
    contribution: number;
    product: string | null;
    label: string;
  }>;
  achievements: Array<{
    key: string;
    label: string;
    description: string;
    icon: string | null;
    rewards: Reward[];
    unlocks: Unlock[];
  }>;
}

const VALUE_ICONS: Record<string, string> = { xp: "sparkles", coins: "coins", contribution: "handshake" };

/**
 * 027: how each look lays the moment out — a card in the middle, a wide banner, an opening crawl, an
 * unrolled scroll, a terminal, comic panels, or a split screen (the number big on one side).
 */
const LAYOUTS: Record<string, string> = {
  crawl: "crawl",
  spell: "scroll",
  onering: "scroll",
  decode: "terminal",
  glitch: "terminal",
  arcade: "terminal",
  comic: "panel",
  manga: "panel",
  hero: "panel",
  boing: "panel",
  hud: "banner",
  minimal: "banner",
  synthwave: "banner",
  spotlight: "banner",
  noir: "split",
  cinema: "split",
  upsidedown: "split",
  sandstorm: "split",
};
/** The big word some looks shout (an onomatopoeia, a code). */
const WORDS: Record<string, string> = {
  comic: "KAPOW!",
  manga: "ドン!",
  hero: "BAM!",
  boing: "BOING!",
  glitch: "LVL_UP",
  decode: "ACCESS GRANTED",
  pumpkin: "BOO!",
  gift: "HO HO HO",
};
/** How many particles each look scatters. */
const PARTICLES: Record<string, number> = {
  arcade: 28,
  cosmic: 36,
  elements: 4,
  crawl: 60,
  decode: 24,
  sandstorm: 40,
  bloodmoon: 14,
  pumpkin: 10,
  gift: 30,
  boing: 10,
  hearth: 24,
  disco: 30,
  upsidedown: 40,
  onering: 24,
  spell: 24,
  abduction: 12,
  minimal: 0,
  noir: 50,
};

function sample(level: number): Summary {
  return {
    level,
    previous: level - 1,
    xp: 0,
    level_floor: 0,
    next_level_at: null,
    rewards: [{ level, coins: 100, contribution: 0, product: null, label: "" }],
    achievements: [
      {
        key: "sample",
        label: "Living legend",
        description: "",
        icon: "crown",
        rewards: [{ value: "coins", amount: 250 }],
        unlocks: [{ product: "level_crown", kind: "level_badge", label: "Crowned level badge" }],
      },
    ],
  };
}

export function LevelUpMoment() {
  const t = useT();
  const format = useFormat();
  const { effective, looks } = useTheme();
  const [event, setEvent] = useState<LevelUpEvent | null>(null);
  useEffect(() => {
    const onLevelUp = (e: Event) => setEvent((e as CustomEvent<LevelUpEvent>).detail);
    window.addEventListener(EVENT, onLevelUp);
    return () => window.removeEventListener(EVENT, onLevelUp);
  }, []);
  const level = event?.level ?? 0;
  const from = event?.from;
  const summary = useQuery({
    queryKey: ["gamification", "level-up", level, from],
    enabled: Boolean(event) && !event?.preview,
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/me/level-ups/{level}", {
          params: { path: { level }, query: from ? { since: from } : {} },
        })
      ).data as unknown as Summary,
  });
  const shop = useQuery({
    queryKey: ["marketplace", "products", "level-up"],
    enabled: Boolean(event) && !event?.preview,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/marketplace/products", {})).data ?? []) as unknown as Product[],
  });
  useEffect(() => {
    if (event) void sound.play("levelUp");
  }, [event]);
  if (!event) return null;
  const look = event.preview ?? looks.levelUp ?? "classic";
  const data = event.preview ? sample(level) : summary.data;
  const previous = data?.previous ?? from ?? level - 1;
  const coins = (data?.rewards ?? []).reduce((sum, r) => sum + r.coins, 0);
  const contribution = (data?.rewards ?? []).reduce((sum, r) => sum + r.contribution, 0);
  const won: Reward[] = [
    ...(event.xp ? [{ value: "xp", amount: event.xp }] : []),
    ...(coins ? [{ value: "coins", amount: coins }] : []),
    ...(contribution ? [{ value: "contribution", amount: contribution }] : []),
    ...(data?.achievements ?? []).flatMap((a) => a.rewards),
  ];
  const totals = won.reduce<Record<string, number>>((acc, r) => {
    acc[r.value] = (acc[r.value] ?? 0) + r.amount;
    return acc;
  }, {});
  const unlocked = [
    ...(data?.achievements ?? []).flatMap((a) => a.unlocks.map((u) => u.label)),
    ...(data?.rewards ?? []).filter((r) => r.product).map((r) => r.label || (r.product as string)),
  ];
  const inShop = (shop.data ?? [])
    .filter(
      (p) => !p.owned && typeof p.min_level === "number" && p.min_level > previous && p.min_level <= level,
    )
    .slice(0, 4);
  const toNext = data?.next_level_at ? Math.max(0, data.next_level_at - data.xp) : null;
  const reduced = effective.reducedMotion;
  return (
    <DialogPrimitive.Root open onOpenChange={(open) => (open ? null : setEvent(null))}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="levelup__overlay" />
        <DialogPrimitive.Content
          className="levelup"
          data-look={look}
          data-layout={LAYOUTS[look] ?? "card"}
          data-reduced={reduced || undefined}
          aria-describedby={undefined}
        >
          <div className="levelup__stage" aria-hidden="true">
            <LevelUpFx look={look} />
          </div>
          <div className="levelup__card">
            <div className="levelup__badge">
              <LevelBadge level={level} label={t("shell:levelLabel", { level })} />
            </div>
            <DialogPrimitive.Title className="levelup__title">
              <span className="levelup__kicker">{t("gamification:levelUp.kicker")}</span>
              {t("gamification:levelUp.title", { level })}
            </DialogPrimitive.Title>
            <p className="levelup__from">{t("gamification:levelUp.from", { from: previous, level })}</p>
            {Object.keys(totals).length ? (
              <section className="levelup__section" aria-label={t("gamification:levelUp.won")}>
                <h3>{t("gamification:levelUp.won")}</h3>
                <ul className="levelup__won">
                  {Object.entries(totals).map(([value, amount], index) => (
                    <li key={value} style={{ "--i": index } as CSSProperties} data-value={value}>
                      <Icon name={VALUE_ICONS[value] ?? "star"} size={18} />
                      <strong>+{format.number(amount)}</strong>
                      <span>{t(`gamification:value.${value}`)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {data?.achievements.length ? (
              <section className="levelup__section" aria-label={t("gamification:levelUp.achievements")}>
                <h3>{t("gamification:levelUp.achievements")}</h3>
                <ul className="levelup__list">
                  {data.achievements.map((a) => (
                    <li key={a.key}>
                      <Icon name={a.icon ?? "trophy"} size={16} />
                      {a.label}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {unlocked.length || inShop.length ? (
              <section className="levelup__section" aria-label={t("gamification:levelUp.unlocked")}>
                <h3>{t("gamification:levelUp.unlocked")}</h3>
                <ul className="levelup__list">
                  {unlocked.map((label) => (
                    <li key={label} data-gift>
                      <Icon name="gift" size={16} />
                      {label}
                    </li>
                  ))}
                  {inShop.map((product) => (
                    <li key={product.key}>
                      <Icon name="shop" size={16} />
                      {t("gamification:levelUp.inShop", { name: product.name })}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {toNext !== null ? (
              <p className="levelup__next">
                {t("gamification:levelUp.next", { xp: format.number(toNext), level: level + 1 })}
              </p>
            ) : null}
            <div className="levelup__actions">
              {event.preview ? null : (
                <Link to="/progression" className="ds-button ds-button--ghost" onClick={() => setEvent(null)}>
                  {t("gamification:levelUp.progression")}
                </Link>
              )}
              <DialogPrimitive.Close className="ds-button ds-button--primary">
                {t("gamification:levelUp.continue")}
              </DialogPrimitive.Close>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** The decoration of each look — layers and particles placed once, animated by CSS. */
function LevelUpFx({ look }: { look: string }) {
  const count = PARTICLES[look] ?? 18;
  const word = WORDS[look];
  return (
    <>
      <span className="levelup__rays" />
      <span className="levelup__scene" />
      {look === "cinema" ? (
        <span className="levelup__countdown">
          {[3, 2, 1].map((n) => (
            <span key={n} style={{ "--n": 3 - n } as CSSProperties}>
              {n}
            </span>
          ))}
        </span>
      ) : null}
      {word ? <span className="levelup__burst">{word}</span> : null}
      {Array.from({ length: count }, (_, i) => (
        <span
          // biome-ignore lint/suspicious/noArrayIndexKey: decorative particles, fixed count
          key={i}
          className="levelup__fx"
          style={
            {
              "--i": i,
              "--n": count,
              "--x": `${(Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1) * 100}%`,
              "--y": `${(Math.abs(Math.sin(i * 78.233) * 12345.678) % 1) * 100}%`,
              "--r": (Math.abs(Math.sin(i * 3.7)) % 1).toFixed(2),
            } as CSSProperties
          }
        />
      ))}
    </>
  );
}
