import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { useProgression } from "../../gamification/api";
import { type Booster, localized, useBoosters, useOpenings } from "./api";
import { BoosterReveal } from "./BoosterReveal";
import "./boosters.css";

const RARITIES = ["common", "rare", "epic", "legendary"] as const;
// each pack's emblem
const EMBLEM: Record<string, string> = {
  cosmos: "sparkles",
  legend: "crown",
  prestige: "gem",
  reserve: "potion",
  discovery: "compass",
  spring: "flower",
  summer: "sun",
  halloween: "ghost",
  winter: "snowflake",
};
// the classic first, then the season's, the dearest, and the smaller ones
const ORDER = [
  "cosmos",
  "spring",
  "summer",
  "halloween",
  "winter",
  "legend",
  "prestige",
  "reserve",
  "discovery",
];

/** The sealed pack itself — foil, a tear line, the booster's name; ``stage`` for the opening. */
export function BoosterPack({ booster, stage = false }: { booster: Booster; stage?: boolean }) {
  const { locale } = useLocaleContext();
  return (
    <span
      className="booster-pack"
      data-theme-pack={booster.theme}
      data-stage={stage || undefined}
      aria-hidden="true"
    >
      <span className="booster-pack__foil" />
      <span className="booster-pack__flap" />
      <span className="booster-pack__stars" />
      <span className="booster-pack__emblem">
        <Icon name={EMBLEM[booster.theme] ?? "sparkles"} size={stage ? 46 : 34} />
      </span>
      <span className="booster-pack__name">{localized(booster.names, locale)}</span>
      <span className="booster-pack__count">×{booster.cards}</span>
    </span>
  );
}

/** Whether I can open it now — and, if not, why. */
export function useCanOpen(booster: Booster) {
  const t = useT();
  const format = useFormat();
  const coins = useProgression().data?.coins;
  if (booster.left === 0) return { ok: false, reason: t("marketplace:booster.noneLeft") };
  if (coins !== undefined && coins < booster.price) {
    return {
      ok: false,
      reason: t("marketplace:booster.notEnough", { coins: format.number(booster.price - coins) }),
    };
  }
  return { ok: true, reason: null };
}

function BoosterOffer({ booster }: { booster: Booster }) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const [open, setOpen] = useState(false);
  const can = useCanOpen(booster);
  const reserve = booster.kind === "reserve";
  return (
    <article className="booster-offer" data-theme-pack={booster.theme}>
      <button
        type="button"
        className="booster-offer__pack"
        onClick={() => setOpen(true)}
        disabled={!can.ok}
        aria-label={t("marketplace:booster.tear", { name: localized(booster.names, locale) })}
      >
        <BoosterPack booster={booster} />
      </button>
      <div className="booster-offer__text">
        <h3>{localized(booster.names, locale)}</h3>
        <p>{localized(booster.descriptions, locale)}</p>
        <p className="booster-offer__facts">
          <span>
            <Icon name="list" size={14} />
            {t("marketplace:booster.cards", { count: booster.cards })}
          </span>
          {booster.guarantee !== "common" ? (
            <span data-rarity={booster.guarantee}>
              <Icon name="shield" size={14} />
              {t("marketplace:booster.guarantee", { rarity: t(`marketplace:rarity.${booster.guarantee}`) })}
            </span>
          ) : null}
          {reserve ? (
            <span>
              <Icon name="potion" size={14} />
              {t("marketplace:booster.goesToReserve")}
            </span>
          ) : null}
          {booster.until ? (
            <span data-season>
              <Icon name="calendar" size={14} />
              {t("marketplace:booster.until", { date: format.date(booster.until) })}
            </span>
          ) : null}
          {booster.left !== null ? (
            <span>
              <Icon name="ticket" size={14} />
              {t("marketplace:booster.left", { count: booster.left })}
            </span>
          ) : null}
        </p>
        <ul className="booster-odds" aria-label={t("marketplace:booster.odds")} data-kind={booster.kind}>
          {RARITIES.filter((rarity) => (booster.odds[rarity] ?? 0) > 0).map((rarity) => (
            <li key={rarity} data-rarity={rarity}>
              <span className="booster-odds__label">{t(`marketplace:rarity.${rarity}`)}</span>
              <span className="booster-odds__bar">
                <span style={{ inlineSize: `${Math.max(2, booster.odds[rarity] ?? 0)}%` }} />
              </span>
              <span className="booster-odds__value">{format.number(booster.odds[rarity] ?? 0)} %</span>
              {reserve ? null : (
                <span
                  className="booster-odds__refund"
                  title={t("marketplace:booster.refundPer", {
                    coins: format.number(booster.refunds[rarity] ?? 0),
                  })}
                >
                  <Icon name="coins" size={12} />+{format.number(booster.refunds[rarity] ?? 0)}
                  <span className="visually-hidden">
                    {t("marketplace:booster.refundPer", {
                      coins: format.number(booster.refunds[rarity] ?? 0),
                    })}
                  </span>
                </span>
              )}
            </li>
          ))}
        </ul>
        <div className="booster-offer__buy">
          <span className="booster-offer__price">
            <Icon name="coins" size={16} />
            {format.number(booster.price)}
          </span>
          <Button onClick={() => setOpen(true)} disabled={!can.ok}>
            <Icon name="sparkles" size={16} />
            {t("marketplace:booster.open")}
          </Button>
          {can.reason ? <span className="booster-offer__why">{can.reason}</span> : null}
        </div>
      </div>
      {open ? <BoosterReveal booster={booster} onClose={() => setOpen(false)} /> : null}
    </article>
  );
}

/** The boosters I opened lately — what came out, what came back. */
function History() {
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
            <strong>{localized(row.names, locale)}</strong>
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
              {t("marketplace:booster.historyLine", {
                price: format.number(row.price),
                count: row.cards.length,
              })}
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

/**
 * #81: the boosters' department — the classic one, the season's, the legendary one, Prestige HD, the
 * reserve's and Discovery: each sealed pack with what it holds, the odds and what a duplicate gives back;
 * opening one charges it and plays the reveal. My latest openings below.
 */
export function BoosterShelf() {
  const t = useT();
  const format = useFormat();
  const boosters = useBoosters();
  const coins = useProgression().data?.coins;
  if (boosters.isPending) return <FunctionalState state="loading" />;
  if (boosters.isError) return <FunctionalState state="unavailable" onRetry={() => boosters.refetch()} />;
  const sorted = [...boosters.data].sort((a, b) => ORDER.indexOf(a.theme) - ORDER.indexOf(b.theme));
  return (
    <section className="booster-shelf">
      <p className="booster-shelf__head">
        {coins !== undefined ? (
          <span className="booster-shelf__balance">
            <Icon name="coins" size={16} />
            {t("marketplace:booster.balance", { coins: format.number(coins) })}
          </span>
        ) : null}
        <Link to="/marketplace/reserve" className="booster-shelf__reserve">
          <Icon name="potion" size={16} />
          {t("marketplace:reserve.title")}
        </Link>
      </p>
      {sorted.map((booster) => (
        <BoosterOffer key={booster.key} booster={booster} />
      ))}
      <History />
    </section>
  );
}
