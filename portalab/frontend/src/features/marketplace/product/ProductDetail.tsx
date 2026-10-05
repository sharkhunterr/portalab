import { Link, useParams } from "react-router";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useProduct } from "../api";
import "../marketplace.css";
import { ProductSheet, PurchaseBar, TryOn } from "./ProductSheet";

/**
 * ``/marketplace/products/:key`` (spec 015 T021; 027 sheet): the product sheet — pre-rendering, rarity,
 * type, description, pack contents, price, copies left, conditions, refund policy — and buying it.
 */
export function ProductDetail() {
  const t = useT();
  const { key = "" } = useParams();
  const product = useProduct(key);
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
  return (
    <div className="ds-stack product-page">
      <PageHeader
        icon="shop"
        title={data.name}
        secondary={
          <Link className="ds-button ds-button--secondary" to="/marketplace">
            {t("marketplace:product.back")}
          </Link>
        }
      />
      <ProductSheet product={data} />
      <div className="product-page__actions">
        <TryOn product={data} />
        <PurchaseBar product={data} />
      </div>
    </div>
  );
}
