import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../../api/client";
import { AdminEmpty, AdminSection, AdminToolbar, SearchBox } from "../../../../design-system/admin/AdminKit";
import { Button } from "../../../../design-system/components/Button";
import { SelectField } from "../../../../design-system/components/Field";
import { Icon } from "../../../../design-system/components/Icon";
import { FunctionalState } from "../../../../design-system/state/FunctionalState";
import { useT } from "../../../../i18n/hooks/useT";
import type { Category, Product } from "../../api";
import { ProductArt } from "../../catalog/ProductArt";
import { withConfirmation } from "../confirm";
import { PresentationDialog } from "../ProductEditor";
import { useCatalogPage } from "./api";

const PAGE = 40;
const STATES = ["available", "unavailable", "draft", "archived"] as const;

/**
 * #98 — the catalogue a page at a time (the whole shop is over a thousand products: drawing them all made
 * the page crawl), searched by name or key, filtered by type and state; each product's presentation,
 * publication and withdrawal as before.
 */
export function CatalogTab({ categories }: { categories: Category[] }) {
  const t = useT();
  const client = useQueryClient();
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [state, setState] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const page = useCatalogPage({ q: q.trim(), type, state, limit });
  const refresh = () => client.invalidateQueries({ queryKey: ["marketplace"] });
  const [message, setMessage] = useState<string | null>(null);
  const run = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setMessage(t("marketplace:admin.done"));
      void refresh();
    },
    onError: () => setMessage(t("marketplace:admin.error")),
  });
  const move = (key: string, transition: "publish" | "unavailable" | "archive") =>
    run.mutate(() =>
      withConfirmation(
        (confirmation) =>
          api.POST("/api/v1/admin/marketplace/products/{key}/{transition}", {
            params: { path: { key, transition } },
            body: { confirmation: confirmation ?? null },
          }),
        () => window.confirm(t("marketplace:admin.confirm")),
      ),
    );
  const types = Object.entries(page.data?.types ?? {}).sort((a, b) => b[1] - a[1]);
  const items = (page.data?.items ?? []) as Product[];
  return (
    <AdminSection
      title={t("marketplace:admin.products")}
      icon="shop"
      description={
        page.data
          ? t("marketplace:shopadmin.catalogCount", { shown: items.length, total: page.data.total })
          : undefined
      }
    >
      <AdminToolbar>
        <SearchBox
          value={q}
          onChange={(value) => {
            setQ(value);
            setLimit(PAGE);
          }}
          label={t("marketplace:shopadmin.findProduct")}
        />
        <SelectField
          label={t("marketplace:shopadmin.type")}
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            setLimit(PAGE);
          }}
        >
          <option value="">{t("marketplace:shopadmin.allTypes")}</option>
          {types.map(([key, count]) => (
            <option key={key} value={key}>
              {t(`marketplace:type.${key}`)} ({count})
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("marketplace:shopadmin.col.state")}
          value={state}
          onChange={(e) => {
            setState(e.target.value);
            setLimit(PAGE);
          }}
        >
          <option value="">{t("marketplace:shopadmin.allStates")}</option>
          {STATES.map((s) => (
            <option key={s} value={s}>
              {t(`marketplace:productState.${s}`)}
            </option>
          ))}
        </SelectField>
      </AdminToolbar>
      {message ? <p role="status">{message}</p> : null}
      {page.isError ? <FunctionalState state="unavailable" onRetry={() => page.refetch()} /> : null}
      {page.isPending ? <FunctionalState state="loading" /> : null}
      {page.data && !items.length ? <AdminEmpty icon="shop" title={t("marketplace:shopadmin.none")} /> : null}
      <ul className="admin-products">
        {items.map((p) => (
          <li key={p.key} className="admin-product" data-rarity={p.rarity ?? "common"}>
            <ProductArt product={p} size="mini" />
            <div className="admin-product__body">
              <strong>{p.name}</strong>
              <span className="widget__meta">
                {t(`marketplace:type.${p.type}`)} · {t(`marketplace:rarity.${p.rarity ?? "common"}`)} · v
                {p.version}
                {p.price_coins ? ` · ${p.price_coins} Coins` : ""}
                {p.supply ? ` · ${p.remaining ?? 0}/${p.supply}` : ""}
                {p.min_level ? ` · ${t("marketplace:card.level", { level: p.min_level })}` : ""}
              </span>
              <span className="ds-badge" data-state={p.state}>
                {t(`marketplace:productState.${p.state}`)}
                {p.featured ? ` · ${t("marketplace:shop.featured")}` : ""}
              </span>
            </div>
            <div className="admin-product__actions">
              <PresentationDialog product={p} categories={categories} onSaved={refresh} />
              {p.state !== "available" && p.state !== "archived" ? (
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label={t("marketplace:admin.publish")}
                  title={t("marketplace:admin.publish")}
                  onClick={() => move(p.key, "publish")}
                >
                  <Icon name="check" size={18} />
                </Button>
              ) : null}
              {p.state === "available" ? (
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label={t("marketplace:admin.unavailable")}
                  title={t("marketplace:admin.unavailable")}
                  onClick={() => move(p.key, "unavailable")}
                >
                  <Icon name="hide" size={18} />
                </Button>
              ) : null}
              {p.state !== "archived" ? (
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label={t("marketplace:admin.archive")}
                  title={t("marketplace:admin.archive")}
                  onClick={() => move(p.key, "archive")}
                >
                  <Icon name="trash" size={18} />
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {page.data && items.length < page.data.total ? (
        <Button variant="secondary" onClick={() => setLimit((n) => n + PAGE)} disabled={page.isFetching}>
          {t("marketplace:shopadmin.more")}
        </Button>
      ) : null}
    </AdminSection>
  );
}
