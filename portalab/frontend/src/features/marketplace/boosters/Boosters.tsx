import type { CSSProperties } from "react";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { CurrencyShort } from "../../../design-system/site/SiteLook";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { useHasPermission } from "../../authz/useMyPermissions";
import { useProgression } from "../../gamification/api";
import type { Product } from "../api";
import {
  type Booster,
  type BoosterInfo,
  boosterOf,
  localized,
  openBooster,
  useBoosters,
  useOpenings,
} from "./api";
import { useSceneBindings } from "./scene/scene";
import "./boosters.css";

const RARITIES = ["common", "rare", "epic", "legendary"] as const;
// each pack's emblem
const EMBLEM: Record<string, string> = {
  cosmos: "sparkles",
  legend: "crown",
  prestige: "gem",
  reserve: "potion",
  discovery: "compass",
  valentine: "heart",
  spring: "flower",
  summer: "sun",
  halloween: "ghost",
  winter: "snowflake",
  christmas: "snowflake",
};

/** What a pack shows: its name, its look, how many cards. */
export interface PackLook {
  names: Record<string, string>;
  look: string;
  cards: number;
  /** issue 234: a content's booster — its title drawn (an art site's logo) in place of its name */
  logo?: string | null;
}

/** The sealed pack itself — foil, a tear line, the booster's name; ``stage`` for the opening, ``card``
 * inside a shop tile, ``mini`` in lists. */
export function BoosterPack({
  booster,
  stage = false,
  size,
}: {
  booster: PackLook;
  stage?: boolean;
  size?: "card" | "mini" | undefined;
}) {
  const { locale } = useLocaleContext();
  return (
    <span
      className="booster-pack"
      data-theme-pack={booster.look}
      data-stage={stage || undefined}
      data-size={size}
      aria-hidden="true"
    >
      <span className="booster-pack__foil" />
      <span className="booster-pack__flap" />
      <span className="booster-pack__stars" />
      <span className="booster-pack__emblem">
        <Icon name={EMBLEM[booster.look] ?? "sparkles"} size={stage ? 46 : size === "mini" ? 18 : 34} />
      </span>
      {size === "mini" ? null : booster.logo ? (
        <img className="booster-pack__logo" src={booster.logo} alt="" draggable={false} />
      ) : (
        <span className="booster-pack__name">{localized(booster.names, locale)}</span>
      )}
      <span className="booster-pack__count">×{booster.cards}</span>
    </span>
  );
}

/**
 * A booster product's pack (its shop tile, its sheet) — issue 153: a booster with a scene of its own shows a card
 * of it face down (its scene's back), else its sealed pack in its scene's look; the scene every booster opens
 * with does not change their tiles.
 */
export function ProductPack({ product, size }: { product: Product; size?: "card" | "mini" | undefined }) {
  const info = boosterOf(product);
  const scene = useSceneBindings()[product.key];
  const booster = { names: product.names, look: info?.look ?? "cosmos", cards: info?.cards ?? 5 };
  if (scene?.card_back) {
    return (
      <span className="booster-scene-card" data-size={size} aria-hidden="true">
        <span
          className="booster-card"
          data-state="hidden"
          data-card-back={scene.card_back}
          style={{ "--i": 0, "--offset": 0 } as CSSProperties}
        >
          <span className="booster-card__inner">
            <span className="booster-card__back">
              <span className="booster-card__back-pattern" />
              <span className="booster-card__back-sigil">
                <Icon name="sparkles" size={size === "mini" ? 10 : 26} />
              </span>
            </span>
          </span>
        </span>
        {size === "mini" ? null : <span className="booster-scene-card__count">×{booster.cards}</span>}
      </span>
    );
  }
  return scene?.booster_look ? (
    <span className="booster-scene-pack" data-booster-look={scene.booster_look} data-size={size}>
      <BoosterPack booster={booster} />
    </span>
  ) : (
    <BoosterPack booster={booster} size={size} />
  );
}

/** Whether I can buy and open it now — and, if not, why. */
export function useCanOpen(booster: Pick<Booster, "left" | "price" | "on_sale"> | null | undefined) {
  const t = useT();
  const format = useFormat();
  const coins = useProgression().data?.coins;
  if (!booster) return { ok: false, reason: null };
  if (!booster.on_sale) return { ok: false, reason: t("marketplace:booster.error.not_available") };
  if (booster.left === 0) return { ok: false, reason: t("marketplace:booster.noneLeft") };
  if (coins !== undefined && coins < booster.price) {
    return {
      ok: false,
      reason: t("marketplace:booster.notEnough", { coins: format.number(booster.price - coins) }),
    };
  }
  return { ok: true, reason: null };
}

/** In a booster's sheet: what it holds — cards, guarantee, odds and what a duplicate gives back. */
export function BoosterDetails({ product }: { product: Product }) {
  const t = useT();
  const format = useFormat();
  const info: BoosterInfo | null = boosterOf(product);
  const mine = useBoosters().data?.find((b) => b.key === product.key);
  if (!info) return null;
  const reserve = info.kind === "reserve";
  return (
    <section className="product-sheet__section booster-details" aria-labelledby="booster-details">
      <h3 id="booster-details">{t("marketplace:booster.contents")}</h3>
      <p className="booster-offer__facts">
        <span>
          <Icon name="list" size={14} />
          {t("marketplace:booster.cards", { count: info.cards })}
        </span>
        {info.guarantee !== "common" ? (
          <span data-rarity={info.guarantee}>
            <Icon name="shield" size={14} />
            {t("marketplace:booster.guarantee", { rarity: t(`marketplace:rarity.${info.guarantee}`) })}
          </span>
        ) : null}
        <span>
          <Icon name={reserve ? "potion" : info.pool === "hd" ? "gem" : "sparkles"} size={14} />
          {t(`marketplace:booster.pool.${info.pool}`)}
        </span>
        {info.season ? (
          <span data-season>
            <Icon name="calendar" size={14} />
            {info.until
              ? t("marketplace:booster.untilSeason", {
                  season: t(`marketplace:season.${info.season}`),
                  date: format.date(info.until),
                })
              : t(`marketplace:season.${info.season}`)}
          </span>
        ) : null}
        {mine?.left !== null && mine?.left !== undefined ? (
          <span>
            <Icon name="ticket" size={14} />
            {t("marketplace:booster.left", { count: mine.left })}
          </span>
        ) : null}
        {mine?.sealed ? (
          <span data-gift>
            <Icon name="gift" size={14} />
            {t("marketplace:booster.sealedCount", { count: mine.sealed })}
          </span>
        ) : null}
      </p>
      <ul className="booster-odds" aria-label={t("marketplace:booster.odds")} data-kind={info.kind}>
        {RARITIES.filter((rarity) => (info.odds[rarity] ?? 0) > 0).map((rarity) => (
          <li key={rarity} data-rarity={rarity}>
            <span className="booster-odds__label">{t(`marketplace:rarity.${rarity}`)}</span>
            <span className="booster-odds__bar">
              <span style={{ inlineSize: `${Math.max(2, info.odds[rarity] ?? 0)}%` }} />
            </span>
            <span className="booster-odds__value">{format.number(info.odds[rarity] ?? 0)} %</span>
            {reserve ? null : (
              <span
                className="booster-odds__refund"
                title={t("marketplace:booster.refundPer", {
                  coins: format.number(info.refunds[rarity] ?? 0),
                })}
              >
                <Icon name="coins" size={12} />+{format.number(info.refunds[rarity] ?? 0)}
                <CurrencyShort />
                <span className="visually-hidden">
                  {t("marketplace:booster.refundPer", { coins: format.number(info.refunds[rarity] ?? 0) })}
                </span>
              </span>
            )}
          </li>
        ))}
      </ul>
      {reserve ? null : <p className="booster-details__note">{t("marketplace:booster.lockedNote")}</p>}
    </section>
  );
}

/** A booster's buy bar: open one bought now, or one of those offered (sealed in my reserve). */
export function BoosterActions({ product }: { product: Product }) {
  const t = useT();
  const format = useFormat();
  const canBuy = useHasPermission("marketplace.purchase");
  const mine = useBoosters().data?.find((b) => b.key === product.key);
  const can = useCanOpen(mine);
  if (!canBuy) return null;
  return (
    <div className="booster-actions">
      {mine?.sealed ? (
        <Button variant="secondary" onClick={() => openBooster(product.key, true)}>
          <Icon name="gift" size={16} />
          {t("marketplace:booster.openSealed", { count: mine.sealed })}
        </Button>
      ) : null}
      <Button onClick={() => openBooster(product.key)} disabled={!can.ok}>
        <Icon name="sparkles" size={16} />
        {t("marketplace:booster.openFor", { price: format.number(mine?.price ?? product.price_coins ?? 0) })}
      </Button>
      {can.reason ? <span className="booster-offer__why">{can.reason}</span> : null}
    </div>
  );
}

/** The boosters I opened lately — what came out, what came back. */
export function BoosterHistory() {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const openings = useOpenings();
  const rows = openings.data ?? [];
  if (!rows.length) return null;
  return (
    <details className="booster-history">
      <summary>
        <Icon name="clock" size={16} />
        {t("marketplace:booster.history")}
      </summary>
      <ul>
        {rows.map((row) => (
          <li key={row.id}>
            <span className="booster-history__when">
              {format.relative((Date.parse(row.opened_at) - Date.now()) / 1000)}
            </span>
            <strong>{localized(row.names, locale) || row.booster}</strong>
            <span className="booster-history__cards">
              {row.cards.map((card, index) => (
                <span
                  // biome-ignore lint/suspicious/noArrayIndexKey: the cards of one opening, in order
                  key={index}
                  className="booster-history__card"
                  data-rarity={card.rarity ?? "common"}
                  data-outcome={card.outcome}
                  title={localized(card.names, locale) || card.product}
                />
              ))}
            </span>
            <span className="booster-history__price">
              {row.price
                ? t("marketplace:booster.historyLine", {
                    price: format.number(row.price),
                    count: row.cards.length,
                  })
                : t("marketplace:booster.historyGift", { count: row.cards.length })}
              {row.refund
                ? ` · ${t("marketplace:booster.historyRefund", { coins: format.number(row.refund) })}`
                : ""}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
