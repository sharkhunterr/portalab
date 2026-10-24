import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { usePacks } from "../../cards/api";
import { CardBoosters } from "../../cards/CardBoosters";
import { type OwnershipRow, usePurchases } from "../api";
import {
  localized,
  openBooster,
  type ReserveEntry,
  requestKey,
  useEarlyUnlock,
  useReserve,
  useUseReserve,
} from "../boosters/api";
import { ProductArt } from "../catalog/ProductArt";
import "../marketplace.css";
import "./reserve.css";

/** issue 131: the items I hold that wait for their level — the level each one waits for. */
function waitingLevel(row: OwnershipRow): number | null {
  const level = row.conditions_snapshot.find((c) => c.kind === "min_level")?.level;
  return typeof level === "number" ? level : null;
}

const NOT_PASSABLE = ["theme", "bundle", "booster", "early_unlock"];

/** issue 131: the items I won (a booster, a gift) but may not wear yet — kept here until their level, and
 * unlocked at once with a level pass when I have one. */
function Waiting({ passKey, onUnlocked }: { passKey: string | null; onUnlocked: (name: string) => void }) {
  const t = useT();
  const purchases = usePurchases();
  const pass = useEarlyUnlock();
  const waiting = (purchases.data ?? []).filter((row) => row.state === "locked");
  if (!waiting.length) return null;
  return (
    <section className="reserve-waiting" aria-labelledby="reserve-waiting-title">
      <h2 id="reserve-waiting-title">
        <Icon name="lock" size={18} />
        {t("marketplace:reserve.waitingTitle")}
      </h2>
      <p className="reserve-waiting__hint">
        {passKey ? t("marketplace:reserve.waitingUnlock") : t("marketplace:reserve.waitingHint")}
      </p>
      <ul className="reserve-pass">
        {waiting.map((row) => (
          <li key={row.id}>
            <span className="reserve-pass__name">
              <strong>{row.product_name}</strong>
              {waitingLevel(row) ? (
                <small>{t("marketplace:reserve.unlockWaits", { level: waitingLevel(row) ?? 0 })}</small>
              ) : null}
            </span>
            {passKey && !NOT_PASSABLE.includes(row.product_type) ? (
              <Button
                variant="secondary"
                disabled={pass.isPending}
                onClick={() =>
                  pass.mutate(
                    { key: passKey, target: row.product_key },
                    { onSuccess: () => onUnlocked(row.product_name) },
                  )
                }
              >
                <Icon name="key" size={14} />
                {t("marketplace:reserve.unlockPick")}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {pass.isError ? <p role="alert">{t("marketplace:reserve.failed")}</p> : null}
    </section>
  );
}

/** issue 131: a level pass — its window lists my items waiting for a level; choosing one unlocks it. */
function PassItem({ entry, onUsed }: { entry: ReserveEntry; onUsed: (name: string) => void }) {
  const t = useT();
  const purchases = usePurchases();
  const pass = useEarlyUnlock();
  const [open, setOpen] = useState(false);
  const waiting = (purchases.data ?? []).filter(
    (row) =>
      row.state === "locked" &&
      !["theme", "bundle", "booster", "card_booster", "early_unlock"].includes(row.product_type),
  );
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Button disabled={pass.isPending}>
          <Icon name="key" size={16} />
          {t("marketplace:reserve.use")}
        </Button>
      }
      title={t("marketplace:reserve.unlockTitle", { name: entry.product.name })}
      description={t("marketplace:reserve.unlockHint")}
      closeLabel={t("marketplace:reserve.cancel")}
    >
      {waiting.length ? (
        <ul className="reserve-pass">
          {waiting.map((row) => (
            <li key={row.id}>
              <span className="reserve-pass__name">
                <strong>{row.product_name}</strong>
                {waitingLevel(row) ? (
                  <small>{t("marketplace:reserve.unlockWaits", { level: waitingLevel(row) ?? 0 })}</small>
                ) : null}
              </span>
              <Button
                variant="secondary"
                disabled={pass.isPending}
                onClick={() =>
                  pass.mutate(
                    { key: entry.product.key, target: row.product_key },
                    {
                      onSuccess: () => {
                        setOpen(false);
                        onUsed(row.product_name);
                      },
                    },
                  )
                }
              >
                <Icon name="lock" size={14} />
                {t("marketplace:reserve.unlockPick")}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p>{t("marketplace:reserve.unlockNone")}</p>
      )}
      {pass.isError ? <p role="alert">{t("marketplace:reserve.failed")}</p> : null}
    </Dialog>
  );
}

function Item({
  entry,
  onUsed,
}: {
  entry: ReserveEntry;
  onUsed: (name: string, ticket: boolean, unlocked?: boolean) => void;
}) {
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
      {entry.early_unlock ? (
        <PassItem entry={entry} onUsed={(unlocked) => onUsed(unlocked, false, true)} />
      ) : entry.booster ? (
        // a sealed booster (offered, or bought earlier): opened on the stage, for free
        <Button onClick={() => openBooster(entry.product.key, true)}>
          <Icon name="gift" size={16} />
          {t("marketplace:reserve.open")}
        </Button>
      ) : (
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
      )}
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
  const [done, setDone] = useState<{ name: string; ticket: boolean; unlocked?: boolean } | null>(null);
  const items = reserve.data ?? [];
  const cardPacks = usePacks().data ?? []; // issue 234: my card boosters wait here too
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
          {done.unlocked
            ? t("marketplace:reserve.unlockUsed", { name: done.name })
            : t("marketplace:reserve.used", { name: done.name })}
          {done.ticket ? <Link to="/marketplace/owned">{t("marketplace:reserve.toConfigure")}</Link> : null}
        </p>
      ) : null}
      {reserve.isPending ? <FunctionalState state="loading" /> : null}
      {reserve.isError ? <FunctionalState state="unavailable" onRetry={() => reserve.refetch()} /> : null}
      <CardBoosters inventory />
      {reserve.data && !items.length && !cardPacks.length ? (
        <div className="reserve__empty">
          <Icon name="potion" size={32} />
          <strong>{t("marketplace:reserve.empty")}</strong>
          <p>{t("marketplace:reserve.emptyHint")}</p>
          <Link to="/marketplace?d=boosters">{t("marketplace:reserve.toBoosters")}</Link>
        </div>
      ) : null}
      <Waiting
        passKey={items.find((entry) => entry.early_unlock)?.product.key ?? null}
        onUnlocked={(name) => setDone({ name, ticket: false, unlocked: true })}
      />
      {items.length ? (
        <ul className="reserve__list">
          {items.map((entry) => (
            <Item
              key={entry.product.key}
              entry={entry}
              onUsed={(name, ticket, unlocked) => setDone({ name, ticket, unlocked: Boolean(unlocked) })}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}
