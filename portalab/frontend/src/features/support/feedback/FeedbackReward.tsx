import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { withConfirmation } from "../../marketplace/admin/confirm";
import { useCatalogPage } from "../../marketplace/admin/console/api";

type Item = components["schemas"]["FeedbackOut"];
type Kind = "coins" | "xp" | "product";

const PRESETS = [50, 100, 250, 500] as const;

/** Whether this viewer may reward this feedback (an author, and a right to give). */
export function useCanReward(item: Item): boolean {
  const canGrant = useHasPermission("rewards.grant");
  const canGift = useHasPermission("marketplace.manage");
  return Boolean(item.submitter_id) && (canGrant || canGift);
}

/**
 * A feedback (or a form's answer) that made a difference earns its author something, at the
 * administrator's will: some of the portal's currency, XP, or a product of the shop — given through the
 * same grants as the member's console, with a thank-you sent as the reply (the member is notified).
 */
export function FeedbackReward({
  item,
  onDone,
  trigger,
  open: shown,
  onOpenChange,
  message: written,
}: {
  item: Item;
  onDone: () => void;
  /** What opens the dialog (a chip of the feedback's actions), a button by default; ``null``: opened by
   * the owner (``open``), e.g. « send and reward » with the reply already written (``message``). */
  trigger?: ReactNode | null;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  message?: string;
}) {
  const t = useT();
  const client = useQueryClient();
  const formId = useId();
  const canGrant = useHasPermission("rewards.grant");
  const canGift = useHasPermission("marketplace.manage");
  const kinds = [...(canGrant ? (["coins", "xp"] as const) : []), ...(canGift ? (["product"] as const) : [])];
  const [own, setOwn] = useState(false);
  const open = shown ?? own;
  const setOpen = (next: boolean) => (onOpenChange ? onOpenChange(next) : setOwn(next));
  const [chosen, setKind] = useState<Kind | null>(null);
  // the rights arrive after the first draw: until a choice is made, the currency when it may be given
  const kind: Kind = chosen ?? (canGrant ? "coins" : "product");
  const [amount, setAmount] = useState("100");
  const [search, setSearch] = useState("");
  const [product, setProduct] = useState<{ key: string; name: string } | null>(null);
  const [message, setMessage] = useState<string | null>(null); // null: the reply already written, if any
  const found = useCatalogPage({ q: search.trim(), type: "", state: "available", limit: 6 });
  const quantity = Math.max(0, Math.floor(Number(amount) || 0));
  const what =
    kind === "product"
      ? (product?.name ?? "")
      : `${quantity} ${t(`marketplace:shopadmin.valueShort.${kind}`)}`;
  // no sentence about the reward: the member sees it as a badge on their feedback (and is notified)
  const thanks = message ?? written?.trim() ?? "";
  const ready = kind === "product" ? Boolean(product) : quantity > 0;
  const give = useMutation({
    mutationFn: async () => {
      // the ledger's reason names the feedback: its first written answer, else its form
      const said = Object.values(item.payload).find(
        (v): v is string => typeof v === "string" && v.trim() !== "",
      );
      const text = (said ?? item.form_label ?? item.kind).slice(0, 120);
      const reason = t("support:reward.reason", { text }).slice(0, 200);
      const always = () => true; // this dialog is the confirmation
      if (kind === "product" && product) {
        await withConfirmation(
          (confirmation) =>
            api.POST("/api/v1/admin/marketplace/grants", {
              body: {
                user_id: item.submitter_id ?? "",
                product: product.key,
                reason,
                quantity: 1,
                confirmation: confirmation ?? null,
              },
            }),
          always,
        );
      } else if (kind !== "product") {
        await withConfirmation(
          (confirmation) =>
            api.POST("/api/v1/admin/gamification/manual-grants", {
              body: {
                user_id: item.submitter_id ?? "",
                value: kind,
                amount: quantity,
                reason,
                // the same reward twice on this feedback (a double click) is given once
                idempotency: `feedback:${item.id}:${kind}:${quantity}`,
                confirmation: confirmation ?? null,
              },
            }),
          always,
        );
      }
      // kept in the feedback's history: what was given
      await api.POST("/api/v1/support/feedback/{feedback_id}/rewarded", {
        params: { path: { feedback_id: item.id } },
        body:
          kind === "product"
            ? { value: "product", product: product?.key ?? null, label: what }
            : { value: kind, amount: quantity, label: what },
      });
      if (thanks.trim()) {
        await api.POST("/api/v1/support/feedback/{feedback_id}/reply", {
          params: { path: { feedback_id: item.id } },
          body: { text: thanks.trim(), append: true },
        });
      }
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["support", "feedback"] });
      setOpen(false);
      onDone();
    },
  });
  if (!item.submitter_id || !kinds.length) return null;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          give.reset();
          setMessage(null);
        }
      }}
      title={t("support:reward.title", { name: item.submitter_name ?? t("support:review.someone") })}
      description={t("support:reward.description")}
      closeLabel={t("support:reward.cancel")}
      trigger={
        trigger === null
          ? null
          : (trigger ?? (
              <Button variant="secondary">
                <Icon name="gift" size={16} />
                {t("support:reward.open")}
              </Button>
            ))
      }
    >
      <form
        id={formId}
        className="feedback-reward"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && !give.isPending) give.mutate();
        }}
      >
        <fieldset className="feedback-reward__kinds">
          <legend className="visually-hidden">{t("support:reward.kind")}</legend>
          {kinds.map((key) => (
            <label key={key} className="feedback-reward__kind" data-checked={kind === key || undefined}>
              <input
                type="radio"
                name={`${formId}-kind`}
                value={key}
                checked={kind === key}
                onChange={() => setKind(key)}
              />
              <Icon name={key === "coins" ? "coins" : key === "xp" ? "sparkles" : "gift"} size={18} />
              {t(`support:reward.kinds.${key}`)}
            </label>
          ))}
        </fieldset>
        {kind === "product" ? (
          <div className="ds-field">
            <label htmlFor={`${formId}-search`}>{t("support:reward.findProduct")}</label>
            <input
              id={`${formId}-search`}
              type="search"
              value={search}
              placeholder={t("support:reward.findHint")}
              onChange={(event) => setSearch(event.target.value)}
            />
            {search.trim() ? (
              <ul className="feedback-reward__products">
                {(found.data?.items ?? []).map((row) => (
                  <li key={row.key}>
                    <label data-checked={product?.key === row.key || undefined}>
                      <input
                        type="radio"
                        name={`${formId}-product`}
                        checked={product?.key === row.key}
                        onChange={() => setProduct({ key: row.key, name: row.name })}
                      />
                      {row.name}
                    </label>
                  </li>
                ))}
                {found.data && !found.data.items.length ? (
                  <li className="admin-muted">{t("support:reward.noProduct")}</li>
                ) : null}
              </ul>
            ) : null}
          </div>
        ) : (
          <div className="ds-field">
            <label htmlFor={`${formId}-amount`}>{t(`support:reward.amount.${kind}`)}</label>
            <div className="feedback-reward__amount">
              <input
                id={`${formId}-amount`}
                type="number"
                min={1}
                max={10000}
                inputMode="numeric"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
              {PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className="feedback-reward__preset"
                  aria-pressed={quantity === preset}
                  onClick={() => setAmount(String(preset))}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="ds-field">
          <label htmlFor={`${formId}-message`}>{t("support:reward.message")}</label>
          <textarea
            id={`${formId}-message`}
            rows={3}
            value={thanks}
            onChange={(event) => setMessage(event.target.value)}
          />
          <small className="admin-muted">{t("support:reward.messageHint")}</small>
        </div>
        {give.isError ? <p role="alert">{t("support:reward.failed")}</p> : null}
        <DialogActions>
          <Button type="submit" disabled={!ready || give.isPending}>
            <Icon name="gift" size={16} />
            {what ? t("support:reward.give", { what }) : t("support:reward.open")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
