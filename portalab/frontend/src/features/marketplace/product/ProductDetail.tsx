import { useState } from "react";
import { Link, useParams } from "react-router";
import { CoinBadge } from "../../../design-system/components/Badges";
import { Button } from "../../../design-system/components/Button";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { useProduct } from "../api";
import { ProductPoster } from "../catalog/ProductPoster";
import { ConditionsChecklist } from "./ConditionsChecklist";
import "../marketplace.css";
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
      <section className="product-hero" data-rarity={data.rarity ?? "common"}>
        <ProductPoster product={data} size="lg" />
        <div className="product-hero__text">
          <span className="product-card__rarity">
            {t(`marketplace:rarity.${data.rarity ?? "common"}`)} · {t(`marketplace:type.${data.type}`)}
          </span>
          <PageHeader title={data.name} context={Object.values(data.descriptions)[0] ?? null} />
          <div className="ds-stack ds-stack--row">
            {data.price_coins ? (
              <CoinBadge amount={data.price_coins} label={t("gamification:value.coins")} />
            ) : (
              <span className="ds-badge">{t("marketplace:purchase.free")}</span>
            )}
            {data.owned ? (
              <span className="product-card__owned">{t("marketplace:product.owned")}</span>
            ) : null}
          </div>
        </div>
      </section>
      <section aria-labelledby="product-conditions" className="ds-stack">
        <h2 id="product-conditions">{t("marketplace:conditions.title")}</h2>
        <ConditionsChecklist checks={data.eligibility ?? []} />
      </section>
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
