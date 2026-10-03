import { useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { useProduct } from "../api";
import { ConditionsChecklist } from "./ConditionsChecklist";
import { PurchaseDialog } from "./PurchaseDialog";

/** ``/marketplace/products/:key`` (spec 015 T021): type, price, named conditions, refund policy, purchase. */
export function ProductDetail() {
  const t = useT();
  const { key = "" } = useParams();
  const product = useProduct(key);
  const canBuy = useHasPermission("marketplace.purchase");
  const [buying, setBuying] = useState(false);
  if (product.isPending) return <FunctionalState state="loading" />;
  if (product.isError || !product.data) {
    return (
      <div className="ds-stack">
        <p>{t("marketplace:product.notFound")}</p>
        <Link to="/marketplace">{t("marketplace:product.back")}</Link>
      </div>
    );
  }
  const data = product.data;
  const eligible = (data.eligibility ?? []).every((c) => c.met);
  return (
    <div className="ds-stack">
      <h1>{data.name}</h1>
      <p className="ds-badge">
        {t(`marketplace:type.${data.type}`)} ·{" "}
        {data.price_coins
          ? t("marketplace:purchase.price", { price: data.price_coins })
          : t("marketplace:purchase.free")}
      </p>
      {Object.values(data.descriptions)[0] ? <p>{Object.values(data.descriptions)[0]}</p> : null}
      <section aria-labelledby="product-conditions" className="ds-stack">
        <h2 id="product-conditions">{t("marketplace:conditions.title")}</h2>
        <ConditionsChecklist checks={data.eligibility ?? []} />
      </section>
      {data.owned ? <p role="status">{t("marketplace:product.owned")}</p> : null}
      {!data.owned && canBuy && data.state === "available" ? (
        buying ? (
          <PurchaseDialog product={data} onClose={() => setBuying(false)} />
        ) : (
          <Button onClick={() => setBuying(true)} disabled={!eligible}>
            {t("marketplace:product.acquire")}
          </Button>
        )
      ) : null}
    </div>
  );
}
