import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { localized, type ReserveEntry, requestKey, useReserve, useUseReserve } from "../boosters/api";
import { ProductArt } from "../catalog/ProductArt";
import "../marketplace.css";
import "./reserve.css";

function Item({ entry, onUsed }: { entry: ReserveEntry; onUsed: (name: string, ticket: boolean) => void }) {
  const t = useT();
  const { locale } = useLocaleContext();
  const use = useUseReserve();
  const [open, setOpen] = useState(false);
  const name = entry.product.name;
  return (
    <li className="reserve-item" data-rarity={entry.product.rarity ?? "common"}>
      <span className="reserve-item__art">
        <ProductArt product={entry.product} size="mini" />
        <span className="reserve-item__count">
          {t("marketplace:reserve.quantity", { count: entry.quantity })}
        </span>
      </span>
      <div className="reserve-item__text">
        <strong>{name}</strong>
        <p>{localized(entry.product.descriptions ?? {}, locale)}</p>
      </div>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        trigger={
          <Button disabled={use.isPending}>
            <Icon name="zap" size={16} />
            {t("marketplace:reserve.use")}
          </Button>
        }
        title={t("marketplace:reserve.useTitle", { name })}
        description={t(
          entry.needs_configuration ? "marketplace:reserve.useTicket" : "marketplace:reserve.useHint",
        )}
        closeLabel={t("marketplace:reserve.cancel")}
        footer={
          <Button
            disabled={use.isPending}
            onClick={() =>
              use.mutate(
                { key: entry.product.key, requestKey: requestKey() },
                {
                  onSuccess: (result) => {
                    setOpen(false);
                    onUsed(name, result.state === "needs_configuration");
                  },
                },
              )
            }
          >
            {t("marketplace:reserve.confirm")}
          </Button>
        }
      >
        {use.isError ? <p role="alert">{t("marketplace:reserve.failed")}</p> : null}
      </Dialog>
    </li>
  );
}

/**
 * #81 ``/marketplace/reserve``: the items won in boosters, kept to use whenever I want — extra requests,
 * streak freezes, boosts, rescues, tickets (a film in 4K, a community project). They stack and never
 * expire; using one grants it now, as if bought (a ticket then waits for its form in « My purchases »).
 */
export default function ReservePage() {
  const t = useT();
  const reserve = useReserve();
  const [done, setDone] = useState<{ name: string; ticket: boolean } | null>(null);
  const items = reserve.data ?? [];
  return (
    <div className="reserve ds-stack">
      <PageHeader
        icon="potion"
        title={t("marketplace:reserve.title")}
        context={t("marketplace:reserve.pitch")}
      />
      {done ? (
        <p className="reserve__done" role="status">
          <Icon name="check" size={16} />
          {t("marketplace:reserve.used", { name: done.name })}
          {done.ticket ? <Link to="/marketplace/owned">{t("marketplace:reserve.toConfigure")}</Link> : null}
        </p>
      ) : null}
      {reserve.isPending ? <FunctionalState state="loading" /> : null}
      {reserve.isError ? <FunctionalState state="unavailable" onRetry={() => reserve.refetch()} /> : null}
      {reserve.data && !items.length ? (
        <div className="reserve__empty">
          <Icon name="potion" size={32} />
          <strong>{t("marketplace:reserve.empty")}</strong>
          <p>{t("marketplace:reserve.emptyHint")}</p>
          <Link to="/marketplace?department=boosters">{t("marketplace:reserve.toBoosters")}</Link>
        </div>
      ) : null}
      {items.length ? (
        <ul className="reserve__list">
          {items.map((entry) => (
            <Item
              key={entry.product.key}
              entry={entry}
              onUsed={(name, ticket) => setDone({ name, ticket })}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}
