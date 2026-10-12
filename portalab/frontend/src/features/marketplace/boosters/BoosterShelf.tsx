import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { type Booster, localized, useBoosters } from "./api";
import { BoosterReveal } from "./BoosterReveal";
import "./boosters.css";

const RARITIES = ["common", "rare", "epic", "legendary"] as const;

/** The sealed pack itself — foil, a tear line, the booster's name; ``size`` for the shelf or the stage. */
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
        <Icon name="sparkles" size={stage ? 46 : 34} />
      </span>
      <span className="booster-pack__name">{localized(booster.names, locale)}</span>
      <span className="booster-pack__count">×{booster.cards}</span>
    </span>
  );
}

function BoosterOffer({ booster }: { booster: Booster }) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const [open, setOpen] = useState(false);
  return (
    <article className="booster-offer">
      <button type="button" className="booster-offer__pack" onClick={() => setOpen(true)}>
        <BoosterPack booster={booster} />
        <span className="visually-hidden">{t("marketplace:booster.open")}</span>
      </button>
      <div className="booster-offer__text">
        <h3>{localized(booster.names, locale)}</h3>
        <p>{localized(booster.descriptions, locale)}</p>
        <p className="booster-offer__facts">
          <span>
            <Icon name="list" size={14} />
            {t("marketplace:booster.cards", { count: booster.cards })}
          </span>
          <span data-rarity={booster.guarantee}>
            <Icon name="shield" size={14} />
            {t("marketplace:booster.guarantee", { rarity: t(`marketplace:rarity.${booster.guarantee}`) })}
          </span>
        </p>
        <ul className="booster-odds" aria-label={t("marketplace:booster.odds")}>
          {RARITIES.map((rarity) => (
            <li key={rarity} data-rarity={rarity}>
              <span className="booster-odds__label">{t(`marketplace:rarity.${rarity}`)}</span>
              <span className="booster-odds__bar">
                <span style={{ inlineSize: `${Math.max(2, booster.odds[rarity] ?? 0)}%` }} />
              </span>
              <span className="booster-odds__value">{format.number(booster.odds[rarity] ?? 0)} %</span>
              <span
                className="booster-odds__refund"
                title={t("marketplace:booster.refundPer", { coins: format.number(booster.refunds?.[rarity] ?? 0) })}
              >
                <Icon name="coins" size={12} />+{format.number(booster.refunds?.[rarity] ?? 0)}
                <span className="visually-hidden">
                  {t("marketplace:booster.refundPer", { coins: format.number(booster.refunds?.[rarity] ?? 0) })}
                </span>
              </span>
            </li>
          ))}
        </ul>
        <div className="booster-offer__buy">
          <span className="booster-offer__price">
            <Icon name="coins" size={16} />
            {format.number(booster.price)}
          </span>
          <Button onClick={() => setOpen(true)}>
            <Icon name="sparkles" size={16} />
            {t("marketplace:booster.open")}
          </Button>
        </div>
        <p className="booster-offer__note">{t("marketplace:booster.previewNote")}</p>
      </div>
      {open ? <BoosterReveal booster={booster} onClose={() => setOpen(false)} /> : null}
    </article>
  );
}

/**
 * #81 (proof of concept): the boosters' department — each sealed pack with what it holds, the odds per
 * rarity and the rarity guaranteed; opening one plays the reveal (nothing is charged or granted yet).
 */
export function BoosterShelf() {
  const boosters = useBoosters();
  if (boosters.isPending) return <FunctionalState state="loading" />;
  if (boosters.isError) return <FunctionalState state="unavailable" onRetry={() => boosters.refetch()} />;
  return (
    <section className="booster-shelf">
      {boosters.data.map((booster) => (
        <BoosterOffer key={booster.key} booster={booster} />
      ))}
    </section>
  );
}
