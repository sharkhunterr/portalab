import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../../../api/client";
import {
  AdminEmpty,
  AdminSection,
  AdminTable,
  SearchBox,
  StatusBadge,
} from "../../../../design-system/admin/AdminKit";
import { Button } from "../../../../design-system/components/Button";
import { SelectField, TextField } from "../../../../design-system/components/Field";
import { Icon } from "../../../../design-system/components/Icon";
import { Dialog } from "../../../../design-system/components/Overlays";
import { useFormat } from "../../../../i18n/format/useFormat";
import { useT } from "../../../../i18n/hooks/useT";
import { ApiError } from "../../../../state/regions";
import { productTypeLabel } from "../../typeLabel";
import { withConfirmation } from "../confirm";
import {
  type InventoryItem,
  type LedgerEntry,
  useCatalogPage,
  useEconomy,
  useInventory,
  useLedger,
  useMembers,
  useNameOf,
  type Value,
} from "./api";
import { Kpis } from "./Kpis";

interface Ask {
  title: string;
  detail?: string | undefined;
  action: string;
  danger?: boolean | undefined;
  /** issue 155: how many copies — asked for a product one may own more than once */
  quantity?: boolean | undefined;
  run: (reason: string, copies: number) => Promise<unknown>;
}

const LIVE = ["active", "needs_configuration", "activation_failed", "locked"];
const VALUES: Value[] = ["coins", "xp", "contribution"];

/**
 * #98 — one member at a time: their balances, Coins (or XP, Contribution) given or taken back, an item
 * given, their inventory (an item taken back, or taken out of the history altogether) and their history
 * (an entry cancelled). Every action asks for a reason; the sensitive ones a confirmation.
 */
export function Members({ selected, onSelect }: { selected: string | null; onSelect: (id: string) => void }) {
  const t = useT();
  const members = useMembers();
  const economy = useEconomy(30);
  const [query, setQuery] = useState("");
  const balances = new Map((economy.data?.holders ?? []).map((h) => [h.user_id, h]));
  const needle = query.trim().toLowerCase();
  const list = (members.data ?? []).filter(
    (m) =>
      !needle ||
      m.login.toLowerCase().includes(needle) ||
      (m.display_name ?? "").toLowerCase().includes(needle),
  );
  return (
    <div className="mk-members">
      <AdminSection title={t("marketplace:shopadmin.members")} icon="users" flush>
        <div className="mk-members__search">
          <SearchBox value={query} onChange={setQuery} label={t("marketplace:shopadmin.findMember")} />
        </div>
        <ul className="mk-members__list">
          {list.map((member) => {
            const balance = balances.get(member.id);
            return (
              <li key={member.id}>
                <button
                  type="button"
                  aria-pressed={selected === member.id}
                  onClick={() => onSelect(member.id)}
                  className="mk-members__item"
                >
                  <Icon name="user" size={18} />
                  <span className="mk-members__name">
                    <strong>{member.display_name ?? member.login}</strong>
                    <small>
                      {t("marketplace:shopadmin.levelShort", { level: balance?.level ?? 1 })} ·{" "}
                      {t("marketplace:shopadmin.coins", { count: balance?.coins ?? 0 })}
                    </small>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </AdminSection>
      {selected ? (
        <MemberConsole
          key={selected}
          userId={selected}
          name={(() => {
            const m = (members.data ?? []).find((x) => x.id === selected);
            return m ? (m.display_name ?? m.login) : selected.slice(0, 8);
          })()}
        />
      ) : (
        <AdminEmpty icon="user" title={t("marketplace:shopadmin.pickMember")} />
      )}
    </div>
  );
}

function MemberConsole({ userId, name }: { userId: string; name: string }) {
  const t = useT();
  const format = useFormat();
  const nameOf = useNameOf();
  const client = useQueryClient();
  const economy = useEconomy(30);
  const inventory = useInventory(userId);
  const ledger = useLedger(userId);
  // #98: every action asks its reason in a small dialog, which is its confirmation too
  const [ask, setAsk] = useState<Ask | null>(null);
  const [reason, setReason] = useState("");
  const [copies, setCopies] = useState("1");
  const [value, setValue] = useState<Value>("coins");
  const [amount, setAmount] = useState("50");
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(null), 4000);
    return () => window.clearTimeout(timer);
  }, [message]);
  const found = useCatalogPage({ q: search.trim(), type: "", state: "available", limit: 6 });
  const balance = (economy.data?.holders ?? []).find((h) => h.user_id === userId);
  const confirm = () => true; // the reason's dialog was the confirmation
  const run = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: async () => {
      // the lists up to date first, then « done »: what is said matches what is shown
      await client.invalidateQueries({ queryKey: ["marketplace", "console"] });
      setMessage({ tone: "ok", text: t("marketplace:admin.done") });
      void client.invalidateQueries({ queryKey: ["marketplace"] });
    },
    onError: (error) => {
      // a known refusal in words (nothing to take back, already cancelled…), else the generic one
      const code = error instanceof ApiError ? error.code : undefined;
      const key = code ? `marketplace:shopadmin.error.${code.replace(/\./g, "_")}` : "";
      const text = key ? t(key) : "";
      setMessage({
        tone: "bad",
        text: text && text !== key && text !== key.split(":")[1] ? text : t("marketplace:admin.error"),
      });
    },
  });
  const request = (next: Ask) => {
    setReason("");
    setCopies("1");
    setAsk(next);
  };
  const count = Math.min(50, Math.max(1, Math.floor(Number(copies) || 1)));
  const quantity = Math.max(0, Math.floor(Number(amount) || 0));
  const give = () =>
    request({
      title: t("marketplace:shopadmin.ask.give", {
        what: `${quantity} ${t(`marketplace:shopadmin.valueShort.${value}`)}`,
        name,
      }),
      action: t("marketplace:shopadmin.give"),
      run: (why) =>
        withConfirmation(
          (confirmation) =>
            api.POST("/api/v1/admin/gamification/manual-grants", {
              body: {
                user_id: userId,
                value,
                amount: quantity,
                reason: why,
                confirmation: confirmation ?? null,
              },
            }),
          confirm,
        ),
    });
  const take = () =>
    request({
      title: t("marketplace:shopadmin.ask.take", {
        what: `${quantity} ${t(`marketplace:shopadmin.valueShort.${value}`)}`,
        name,
      }),
      action: t("marketplace:shopadmin.take"),
      danger: true,
      run: (why) =>
        api.POST("/api/v1/admin/gamification/manual-withdrawals", {
          body: { user_id: userId, value, amount: quantity, reason: why },
        }),
    });
  const offer = (product: string, productName: string, repeatable: boolean) =>
    request({
      title: t("marketplace:shopadmin.ask.offer", { what: productName, name }),
      action: t("marketplace:admin.grant"),
      quantity: repeatable,
      run: (why, many) =>
        withConfirmation(
          (confirmation) =>
            api.POST("/api/v1/admin/marketplace/grants", {
              body: {
                user_id: userId,
                product,
                reason: why,
                quantity: many,
                confirmation: confirmation ?? null,
              },
            }),
          confirm,
        ),
    });
  const takeBack = (item: InventoryItem) =>
    request({
      title: t("marketplace:shopadmin.ask.takeBack", { what: nameOf(item.names, item.product), name }),
      action: t("marketplace:shopadmin.takeBack"),
      danger: true,
      run: (why) =>
        withConfirmation(
          (confirmation) =>
            api.POST("/api/v1/admin/marketplace/ownerships/{ownership_id}/revoke", {
              params: { path: { ownership_id: item.ownership_id } },
              body: { ground: "withdrawn_for_cause", reason: why, confirmation: confirmation ?? null },
            }),
          confirm,
        ),
    });
  const erase = (item: InventoryItem) =>
    request({
      title: t("marketplace:shopadmin.ask.erase", { what: nameOf(item.names, item.product) }),
      detail: t("marketplace:shopadmin.eraseConfirm"),
      action: t("marketplace:shopadmin.erase"),
      danger: true,
      run: (why) =>
        api.DELETE("/api/v1/admin/marketplace/ownerships/{ownership_id}", {
          params: { path: { ownership_id: item.ownership_id } },
          body: { reason: why },
        }),
    });
  const cancel = (entry: LedgerEntry) =>
    request({
      title: t("marketplace:shopadmin.ask.cancel"),
      detail: t("marketplace:shopadmin.cancelHint"),
      action: t("marketplace:shopadmin.cancel"),
      danger: true,
      run: (why) =>
        api.POST("/api/v1/admin/economy/transactions/{transaction_id}/reverse", {
          params: { path: { transaction_id: entry.id } },
          body: { reason: why },
        }),
    });
  const reversed = new Set((ledger.data ?? []).map((e) => e.reverses_transaction_id).filter(Boolean));
  return (
    <div className="mk-member">
      {message ? (
        // #98: said where it is seen — floating at the bottom, whatever was clicked
        <p role="status" className="mk-member__toast" data-tone={message.tone}>
          <Icon name={message.tone === "ok" ? "check" : "alert"} size={16} />
          {message.text}
        </p>
      ) : null}
      <Dialog
        open={ask !== null}
        onOpenChange={(open) => {
          if (!open) setAsk(null);
        }}
        title={ask?.title ?? ""}
        {...(ask?.detail ? { description: ask.detail } : {})}
        closeLabel={t("marketplace:admin.cancel")}
        trigger={<span hidden />}
        footer={
          <Button
            variant={ask?.danger ? "danger" : "primary"}
            disabled={reason.trim().length < 3 || run.isPending}
            onClick={() => {
              const current = ask;
              if (!current) return;
              setAsk(null);
              run.mutate(() => current.run(reason.trim(), current.quantity ? count : 1));
            }}
          >
            {ask?.action}
          </Button>
        }
      >
        {ask?.quantity ? (
          <TextField
            label={t("marketplace:shopadmin.quantity")}
            hint={t("marketplace:shopadmin.quantityHint")}
            type="number"
            min={1}
            max={50}
            value={copies}
            onChange={(e) => setCopies(e.target.value)}
          />
        ) : null}
        <TextField
          label={t("marketplace:shopadmin.reason")}
          hint={t("marketplace:shopadmin.reasonHint")}
          value={reason}
          maxLength={200}
          autoFocus
          onChange={(e) => setReason(e.target.value)}
        />
      </Dialog>
      <AdminSection title={name} icon="user">
        <Kpis
          label={name}
          items={[
            {
              key: "level",
              icon: "trending",
              label: t("marketplace:shopadmin.col.level"),
              value: balance?.level ?? 1,
            },
            { key: "xp", icon: "star", label: "XP", value: format.number(balance?.xp ?? 0) },
            {
              key: "coins",
              icon: "coins",
              tone: "ok",
              label: t("marketplace:shopadmin.col.coins"),
              value: format.number(balance?.coins ?? 0),
            },
            {
              key: "contribution",
              icon: "gift",
              tone: "muted",
              label: t("marketplace:shopadmin.contribution"),
              value: format.number(balance?.contribution ?? 0),
            },
          ]}
        />
      </AdminSection>
      <AdminSection title={t("marketplace:shopadmin.balances")} icon="coins">
        <div className="mk-member__row">
          <SelectField
            label={t("marketplace:shopadmin.value")}
            value={value}
            onChange={(e) => setValue(e.target.value as Value)}
          >
            {VALUES.map((v) => (
              <option key={v} value={v}>
                {t(`marketplace:shopadmin.valueName.${v}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("marketplace:shopadmin.amount")}
            type="number"
            min={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
          <Button disabled={!quantity || run.isPending} onClick={give}>
            <Icon name="plus" size={16} />
            {t("marketplace:shopadmin.give")}
          </Button>
          <Button variant="secondary" disabled={!quantity || run.isPending} onClick={take}>
            <Icon name="minus" size={16} />
            {t("marketplace:shopadmin.take")}
          </Button>
        </div>
      </AdminSection>
      <AdminSection title={t("marketplace:shopadmin.giveItem")} icon="gift">
        <SearchBox value={search} onChange={setSearch} label={t("marketplace:shopadmin.findProduct")} />
        {search.trim() ? (
          <ul className="mk-member__found">
            {(found.data?.items ?? []).map((product) => (
              <li key={product.key}>
                <span className="mk-console__product">
                  <strong>{product.name}</strong>
                  <small>
                    {productTypeLabel(t, product.type)} ·{" "}
                    {t(`marketplace:rarity.${product.rarity ?? "common"}`)}
                  </small>
                </span>
                <Button
                  disabled={run.isPending}
                  onClick={() => offer(product.key, product.name, Boolean(product.repeatable))}
                >
                  {t("marketplace:admin.grant")}
                </Button>
              </li>
            ))}
            {found.data && !found.data.items.length ? <li>{t("marketplace:shopadmin.none")}</li> : null}
          </ul>
        ) : null}
      </AdminSection>
      <AdminSection title={t("marketplace:shopadmin.inventory")} icon="list" flush>
        <AdminTable
          label={t("marketplace:shopadmin.inventory")}
          rows={inventory.data ?? []}
          rowKey={(row) => row.ownership_id}
          empty={<AdminEmpty icon="list" title={t("marketplace:shopadmin.emptyInventory")} />}
          columns={[
            {
              key: "product",
              header: t("marketplace:shopadmin.col.product"),
              primary: true,
              render: (row) => (
                <span className="mk-console__product">
                  <strong>{nameOf(row.names, row.product)}</strong>
                  <small>{productTypeLabel(t, row.type)}</small>
                </span>
              ),
            },
            {
              key: "origin",
              header: t("marketplace:shopadmin.col.origin"),
              render: (row) =>
                `${t(`marketplace:shopadmin.origin.${row.origin}`)}${row.price_paid ? ` · ${t("marketplace:shopadmin.coins", { count: row.price_paid })}` : ""}`,
            },
            {
              key: "when",
              header: t("marketplace:shopadmin.col.when"),
              render: (row) => format.date(row.acquired_at),
            },
            {
              key: "state",
              header: t("marketplace:shopadmin.col.state"),
              render: (row) => (
                <StatusBadge tone={LIVE.includes(row.state) ? "ok" : row.refunded ? "warn" : "neutral"}>
                  {t(`marketplace:shopadmin.state.${LIVE.includes(row.state) ? "live" : row.state}`)}
                </StatusBadge>
              ),
            },
          ]}
          actions={(row) => (
            <span className="mk-member__actions">
              {LIVE.includes(row.state) ? (
                <Button variant="secondary" disabled={run.isPending} onClick={() => takeBack(row)}>
                  {t("marketplace:shopadmin.takeBack")}
                </Button>
              ) : null}
              {!row.refunded ? (
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={t("marketplace:shopadmin.erase")}
                  title={t("marketplace:shopadmin.erase")}
                  disabled={run.isPending}
                  onClick={() => erase(row)}
                >
                  <Icon name="trash" size={16} />
                </Button>
              ) : null}
            </span>
          )}
        />
      </AdminSection>
      <AdminSection title={t("marketplace:shopadmin.history")} icon="clock" flush>
        <AdminTable
          label={t("marketplace:shopadmin.history")}
          rows={ledger.data ?? []}
          rowKey={(row) => row.id}
          empty={<AdminEmpty icon="clock" title={t("marketplace:shopadmin.emptyHistory")} />}
          columns={[
            {
              key: "when",
              header: t("marketplace:shopadmin.col.when"),
              render: (row) => format.dateTime(row.occurred_at),
            },
            {
              key: "what",
              header: t("marketplace:shopadmin.col.what"),
              primary: true,
              render: (row) =>
                row.reason ??
                (row.rule_key
                  ? t("marketplace:shopadmin.byRule", { rule: row.rule_key })
                  : t(`marketplace:shopadmin.ledgerKind.${row.source_kind}`)),
            },
            {
              key: "delta",
              header: t("marketplace:shopadmin.col.amount"),
              align: "end",
              render: (row) => (
                <span data-tone={row.delta >= 0 ? "ok" : "bad"} className="mk-member__delta">
                  {row.delta > 0 ? "+" : ""}
                  {format.number(row.delta)} {t(`marketplace:shopadmin.valueShort.${row.value}`)}
                </span>
              ),
            },
          ]}
          actions={(row) =>
            row.reverses_transaction_id || reversed.has(row.id) ? (
              <small className="media-muted">
                {t(
                  row.reverses_transaction_id
                    ? "marketplace:shopadmin.isCancel"
                    : "marketplace:shopadmin.cancelled",
                )}
              </small>
            ) : (
              <Button
                variant="ghost"
                disabled={run.isPending}
                onClick={() => cancel(row)}
                title={t("marketplace:shopadmin.cancelHint")}
              >
                <Icon name="undo" size={14} />
                {t("marketplace:shopadmin.cancel")}
              </Button>
            )
          }
        />
      </AdminSection>
    </div>
  );
}
