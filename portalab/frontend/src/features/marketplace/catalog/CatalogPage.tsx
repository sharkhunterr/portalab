import { useState } from "react";
import { Link } from "react-router";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useCategories, useProducts } from "../api";
import { ProductCard } from "./ProductCard";
import "../marketplace.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/** ``/marketplace`` (spec 015 T021): categories, search and products bought with Coins (no real money). */
export default function CatalogPage() {
  const t = useT();
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const categories = useCategories();
  const products = useProducts({ category, q: q.trim() });
  return (
    <div className="ds-stack">
      <PageHeader
        icon="shop"
        title={t("marketplace:catalog.title")}
        context={t("marketplace:catalog.intro")}
        secondary={
          <>
            <Link className="ds-button ds-button--secondary" to="/projects">
              {t("marketplace:projects.title")}
            </Link>
            <Link className="ds-button ds-button--primary" to="/marketplace/owned">
              {t("marketplace:owned.title")}
            </Link>
          </>
        }
      />
      <div className="ds-stack--row community-filters">
        <SelectField
          label={t("marketplace:catalog.category")}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">{t("marketplace:catalog.all")}</option>
          {(categories.data ?? []).map((c) => (
            <option key={c.key} value={c.key}>
              {t(c.label_key)}
            </option>
          ))}
        </SelectField>
        <TextField
          type="search"
          label={t("marketplace:catalog.search")}
          value={q}
          maxLength={64}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      {products.isError ? <FunctionalState state="unavailable" onRetry={() => products.refetch()} /> : null}
      {products.data?.length === 0 ? <p>{t("marketplace:catalog.empty")}</p> : null}
      <ul className="project-grid">
        {(products.data ?? []).map((product) => (
          <ProductCard key={product.key} product={product} />
        ))}
      </ul>
    </div>
  );
}
