import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Product, useAcquire } from "../api";

/** Purchase confirmation (spec 015 T024): price and refund policy restated before the Coins move. */
export function PurchaseDialog({ product, onClose }: { product: Product; onClose: () => void }) {
  const t = useT();
  const acquire = useAcquire(product.key);
  const [requestKey] = useState(() => crypto.randomUUID());
  const policy = product.refund_policy as { refundable?: boolean; window_days?: number; percent?: number };
  const error = acquire.error instanceof ApiError ? acquire.error.code : null;
  return (
    <div role="dialog" aria-modal="false" aria-labelledby="purchase-title" className="ds-card ds-stack">
      <h2 id="purchase-title">{t("marketplace:purchase.title", { product: product.name })}</h2>
      <p>
        {product.price_coins
          ? t("marketplace:purchase.price", { price: product.price_coins })
          : t("marketplace:purchase.free")}
      </p>
      <p>
        {policy.refundable
          ? t("marketplace:purchase.refundable", {
              days: policy.window_days ?? 0,
              percent: policy.percent ?? 100,
            })
          : t("marketplace:purchase.notRefundable")}
      </p>
      {acquire.isSuccess ? (
        <p role="status">{t(`marketplace:purchase.done.${acquire.data?.state ?? "active"}`)}</p>
      ) : null}
      {error ? (
        <p role="alert">{t(`marketplace:purchase.error.${error.split(".")[1] ?? "generic"}`)}</p>
      ) : null}
      <div className="ds-stack--row">
        {acquire.isSuccess ? null : (
          <Button onClick={() => acquire.mutate(requestKey)} disabled={acquire.isPending}>
            {t("marketplace:purchase.confirm")}
          </Button>
        )}
        <Button variant="secondary" onClick={onClose}>
          {t("marketplace:purchase.close")}
        </Button>
      </div>
    </div>
  );
}
