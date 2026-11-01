import { type ButtonHTMLAttributes, type ReactNode, useEffect, useState } from "react";
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
import { useCollectsCards } from "../../cards/collects";
import { type OwnershipRow, type Product, useProducts, usePurchases } from "../api";
import {
  localized,
  openBooster,
  type ReserveEntry,
  requestKey,
  useEarlyUnlock,
  useReserve,
  useReserveSeen,
  useUseReserve,
} from "../boosters/api";
import { ProductArt } from "../catalog/ProductArt";
import { NeedsConfiguration } from "../owned/Configure";
import "../marketplace.css";
import "./reserve.css";

/** issue 131: the items I hold that wait for their level — the level each one waits for. */
function waitingLevel(row: OwnershipRow): number | null {
  const level = row.conditions_snapshot.find((c) => c.kind === "min_level")?.level;
  return typeof level === "number" ? level : null;
}

const NOT_PASSABLE = ["theme", "bundle", "booster", "card_booster", "early_unlock"];

type Done = { name: string; ticket: boolean; unlocked?: boolean };

/** issue 303: one thing of my reserve as a tile — its art, how many, its name and what it waits for; a tap
 * opens its window (or its booster). The other props go to its button: a window's trigger hands its own. */
function Tile({
  art,
  name,
  count,
  note,
  tone,
  rarity,
  ...rest
}: {
  art: ReactNode;
  name: string;
  count?: number | undefined;
  note?: string | undefined;
  tone?: "todo" | "locked";
  rarity?: string | null | undefined;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const t = useT();
  return (
    <li className="reserve-tile" data-tone={tone} data-rarity={rarity ?? "common"}>
      <button type="button" className="reserve-tile__button" {...rest}>
        <span className="reserve-tile__art">
          {art}
          {count && count > 1 ? (
            <span className="reserve-tile__count">{t("marketplace:reserve.quantity", { count })}</span>
          ) : null}
          {tone === "locked" ? (
            <span className="reserve-tile__lock">
              <Icon name="lock" size={14} />
            </span>
          ) : null}
        </span>
        <span className="reserve-tile__name">{name}</span>
        {note ? <span className="reserve-tile__note">{note}</span> : null}
      </button>
    </li>
  );
}

function Section({
  id,
  icon,
  title,
  hint,
  children,
}: {
  id: string;
  icon: string;
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="reserve-section" id={id} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>
        <Icon name={icon} size={18} />
        {title}
      </h2>
      {hint ? <p className="reserve-section__hint">{hint}</p> : null}
      {children}
    </section>
  );
}

/** issue 303: a purchase that waits for my choices (a project to name, a film to pick) — its form in a window. */
function TodoTile({ row, product }: { row: OwnershipRow; product: Product | undefined }) {
  const t = useT();
  return (
    <Dialog
      trigger={
        <Tile
          art={product ? <ProductArt product={product} size="mini" /> : <Icon name="sparkles" size={28} />}
          name={row.product_name}
          note={t("marketplace:reserve.complete")}
          tone="todo"
          rarity={product?.rarity}
        />
      }
      title={t("marketplace:reserve.completeTitle", { name: row.product_name })}
      closeLabel={t("marketplace:reserve.cancel")}
    >
      <NeedsConfiguration row={row} />
    </Dialog>
  );
}

/** An item to use: its window tells what it does and uses one. */
function UseTile({ entry, onUsed }: { entry: ReserveEntry; onUsed: (done: Done) => void }) {
  const t = useT();
  const { locale } = useLocaleContext();
  const use = useUseReserve();
  const [open, setOpen] = useState(false);
  const name = entry.product.name;
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Tile
          art={<ProductArt product={entry.product} size="mini" />}
          name={name}
          count={entry.quantity}
          rarity={entry.product.rarity}
        />
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
                  onUsed({ name, ticket: result.state === "needs_configuration" });
                },
              },
            )
          }
        >
          <Icon name="zap" size={16} />
          {t("marketplace:reserve.confirm")}
        </Button>
      }
    >
      <div className="reserve-sheet">
        <ProductArt product={entry.product} size="card" />
        <div className="reserve-sheet__text">
          <p>{localized(entry.product.descriptions ?? {}, locale)}</p>
          <p className="reserve-sheet__count">{t("marketplace:reserve.left", { count: entry.quantity })}</p>
        </div>
      </div>
      {use.isError ? <p role="alert">{t("marketplace:reserve.failed")}</p> : null}
    </Dialog>
  );
}

/** issue 131: a level pass — its window lists my items waiting for a level; choosing one unlocks it. */
function PassTile({
  entry,
  waiting,
  onUsed,
}: {
  entry: ReserveEntry;
  waiting: OwnershipRow[];
  onUsed: (done: Done) => void;
}) {
  const t = useT();
  const pass = useEarlyUnlock();
  const [open, setOpen] = useState(false);
  const passable = waiting.filter((row) => !NOT_PASSABLE.includes(row.product_type));
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Tile
          art={<ProductArt product={entry.product} size="mini" />}
          name={entry.product.name}
          count={entry.quantity}
          rarity={entry.product.rarity}
        />
      }
      title={t("marketplace:reserve.unlockTitle", { name: entry.product.name })}
      description={t("marketplace:reserve.unlockHint")}
      closeLabel={t("marketplace:reserve.cancel")}
    >
      {passable.length ? (
        <ul className="reserve-pass">
          {passable.map((row) => (
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
                        onUsed({ name: row.product_name, ticket: false, unlocked: true });
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

/** issue 131: an item I won but may not wear yet — its window tells its level, and unlocks it with a pass. */
function LockedTile({
  row,
  product,
  passKey,
  onUsed,
}: {
  row: OwnershipRow;
  product: Product | undefined;
  passKey: string | null;
  onUsed: (done: Done) => void;
}) {
  const t = useT();
  const pass = useEarlyUnlock();
  const [open, setOpen] = useState(false);
  const level = waitingLevel(row);
  const passable = passKey && !NOT_PASSABLE.includes(row.product_type);
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Tile
          art={product ? <ProductArt product={product} size="mini" /> : <Icon name="lock" size={28} />}
          name={row.product_name}
          note={level ? t("marketplace:reserve.unlockWaits", { level }) : undefined}
          tone="locked"
          rarity={product?.rarity}
        />
      }
      title={row.product_name}
      description={t(passable ? "marketplace:reserve.waitingUnlock" : "marketplace:reserve.waitingHint")}
      closeLabel={t("marketplace:reserve.cancel")}
      footer={
        passable ? (
          <Button
            disabled={pass.isPending}
            onClick={() =>
              pass.mutate(
                { key: passKey, target: row.product_key },
                {
                  onSuccess: () => {
                    setOpen(false);
                    onUsed({ name: row.product_name, ticket: false, unlocked: true });
                  },
                },
              )
            }
          >
            <Icon name="key" size={14} />
            {t("marketplace:reserve.unlockPick")}
          </Button>
        ) : undefined
      }
    >
      {product ? (
        <div className="reserve-sheet">
          <ProductArt product={product} size="card" />
          {level ? (
            <p className="reserve-sheet__count">{t("marketplace:reserve.unlockWaits", { level })}</p>
          ) : null}
        </div>
      ) : null}
      {pass.isError ? <p role="alert">{t("marketplace:reserve.failed")}</p> : null}
    </Dialog>
  );
}

/**
 * #81 ``/marketplace/reserve`` (issue 303 redesign): what I hold to use whenever I want, by what it waits
 * for — a form to fill (a purchase to complete: a community project, a film in 4K…), boosters to open,
 * items to use (extra requests, streak freezes, boosts, rescues, passes), items waiting for their level —
 * each as a tile, its window opened by a tap. A jump bar on top says how many of each.
 */
export default function ReservePage() {
  const t = useT();
  const reserve = useReserve();
  const purchases = usePurchases();
  const products = useProducts({ category: "", q: "" });
  const seen = useReserveSeen();
  const loaded = reserve.isSuccess;
  // biome-ignore lint/correctness/useExhaustiveDependencies: once per visit, when the reserve is shown
  useEffect(() => {
    if (loaded) seen.mutate();
  }, [loaded]);
  const [done, setDone] = useState<Done | null>(null);
  const items = reserve.data ?? [];
  const collects = useCollectsCards(); // issue 243: not for a member who plays without the cards
  const packs = usePacks().data ?? []; // issue 234: my card boosters wait here too
  const cardPacks = collects ? packs : [];
  const byKey = new Map((products.data ?? []).map((p) => [p.key, p]));
  const rows = purchases.data ?? [];
  const todo = rows.filter((row) => row.state === "needs_configuration");
  const locked = rows.filter((row) => row.state === "locked");
  const boosters = items.filter((entry) => entry.booster);
  const usable = items.filter((entry) => !entry.booster);
  const passKey = items.find((entry) => entry.early_unlock)?.product.key ?? null;
  const counts = {
    todo: todo.length,
    open: cardPacks.length + boosters.reduce((sum, entry) => sum + entry.quantity, 0),
    use: usable.reduce((sum, entry) => sum + entry.quantity, 0),
    waiting: locked.length,
  };
  const sections = [
    { key: "todo", icon: "sparkles" },
    { key: "open", icon: "gift" },
    { key: "use", icon: "zap" },
    { key: "waiting", icon: "lock" },
  ] as const;
  const shown = sections.filter((section) => counts[section.key] > 0);
  const empty = reserve.isSuccess && purchases.isSuccess && !shown.length;
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
            : t(done.ticket ? "marketplace:reserve.usedTicket" : "marketplace:reserve.used", {
                name: done.name,
              })}
        </p>
      ) : null}
      {reserve.isPending ? <FunctionalState state="loading" /> : null}
      {reserve.isError ? <FunctionalState state="unavailable" onRetry={() => reserve.refetch()} /> : null}
      {shown.length > 1 ? (
        <nav className="reserve-jump" aria-label={t("marketplace:reserve.jump")}>
          {shown.map((section) => (
            <button
              key={section.key}
              type="button"
              data-tone={section.key === "todo" ? "todo" : undefined}
              onClick={() =>
                document.getElementById(`reserve-${section.key}`)?.scrollIntoView({ behavior: "smooth" })
              }
            >
              <Icon name={section.icon} size={16} />
              {t(`marketplace:reserve.section.${section.key}`)}
              <span className="reserve-jump__count">{counts[section.key]}</span>
            </button>
          ))}
        </nav>
      ) : null}
      {empty ? (
        <div className="reserve__empty">
          <Icon name="potion" size={32} />
          <strong>{t("marketplace:reserve.empty")}</strong>
          <p>{t("marketplace:reserve.emptyHint")}</p>
          <Link to="/marketplace?d=boosters">{t("marketplace:reserve.toBoosters")}</Link>
        </div>
      ) : null}
      {todo.length ? (
        <Section
          id="reserve-todo"
          icon="sparkles"
          title={t("marketplace:reserve.section.todo")}
          hint={t("marketplace:reserve.todoHint")}
        >
          <ul className="reserve-tiles">
            {todo.map((row) => (
              <TodoTile key={row.id} row={row} product={byKey.get(row.product_key)} />
            ))}
          </ul>
        </Section>
      ) : null}
      {counts.open ? (
        <Section id="reserve-open" icon="gift" title={t("marketplace:reserve.section.open")}>
          {boosters.length ? (
            <ul className="reserve-tiles">
              {boosters.map((entry) => (
                // a sealed booster (offered, or bought earlier): opened on the stage, for free
                <Tile
                  key={entry.product.key}
                  art={<ProductArt product={entry.product} size="mini" />}
                  name={entry.product.name}
                  count={entry.quantity}
                  note={t("marketplace:reserve.open")}
                  rarity={entry.product.rarity}
                  onClick={() => openBooster(entry.product.key, true)}
                />
              ))}
            </ul>
          ) : null}
          {collects ? (
            <div className="reserve-rail">
              <CardBoosters inventory />
            </div>
          ) : null}
        </Section>
      ) : null}
      {usable.length ? (
        <Section
          id="reserve-use"
          icon="zap"
          title={t("marketplace:reserve.section.use")}
          hint={t("marketplace:reserve.useSectionHint")}
        >
          <ul className="reserve-tiles">
            {usable.map((entry) =>
              entry.early_unlock ? (
                <PassTile key={entry.product.key} entry={entry} waiting={locked} onUsed={setDone} />
              ) : (
                <UseTile key={entry.product.key} entry={entry} onUsed={setDone} />
              ),
            )}
          </ul>
        </Section>
      ) : null}
      {locked.length ? (
        <Section
          id="reserve-waiting"
          icon="lock"
          title={t("marketplace:reserve.section.waiting")}
          hint={t(passKey ? "marketplace:reserve.waitingUnlock" : "marketplace:reserve.waitingHint")}
        >
          <ul className="reserve-tiles">
            {locked.map((row) => (
              <LockedTile
                key={row.id}
                row={row}
                product={byKey.get(row.product_key)}
                passKey={passKey}
                onUsed={setDone}
              />
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  );
}
