import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { type Column, Table } from "../../../design-system/components/Layout";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type OwnershipRow, type Product, useOwnedActions, useProducts, usePurchases } from "../api";
import { DEPARTMENTS, departmentOf, departmentOfProduct } from "../catalog/CatalogPage";
import { ProductArt } from "../catalog/ProductArt";
import "../marketplace.css";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { MyRequests, RequestForm } from "./Requests";

/** 027: a bought project launch — name the project and pitch it; it opens as a community proposal. */
function ProjectLaunchForm({ row }: { row: OwnershipRow }) {
  const t = useT();
  const { configure } = useOwnedActions();
  const [title, setTitle] = useState("");
  const [pitch, setPitch] = useState("");
  return (
    <form
      className="ds-stack project-launch"
      onSubmit={(event) => {
        event.preventDefault();
        configure.mutate({ id: row.id, configuration: { title, pitch } });
      }}
    >
      <p className="ds-field__hint">{t("marketplace:owned.launchHint")}</p>
      <TextField
        label={t("marketplace:owned.launchTitle")}
        value={title}
        required
        maxLength={200}
        onChange={(e) => setTitle(e.target.value)}
      />
      <div className="ds-field">
        <label htmlFor={`pitch-${row.id}`}>{t("marketplace:owned.launchPitch")}</label>
        <textarea
          id={`pitch-${row.id}`}
          rows={4}
          maxLength={2000}
          value={pitch}
          onChange={(e) => setPitch(e.target.value)}
        />
      </div>
      <Button type="submit" disabled={!title.trim() || configure.isPending}>
        {t("marketplace:owned.launch")}
      </Button>
    </form>
  );
}

function NeedsConfiguration({ row }: { row: OwnershipRow }) {
  const t = useT();
  const { configure } = useOwnedActions();
  const [value, setValue] = useState("");
  if (row.product_type === "project_launch") return <ProjectLaunchForm row={row} />;
  if (row.product_type === "special_request") return <RequestForm row={row} />; // 027: a film in 4K…
  return (
    <form
      className="ds-stack--row"
      onSubmit={(event) => {
        event.preventDefault();
        configure.mutate({ id: row.id, configuration: { value } });
      }}
    >
      <TextField
        label={t("marketplace:owned.configureLabel")}
        value={value}
        required
        onChange={(e) => setValue(e.target.value)}
      />
      <Button type="submit">{t("marketplace:owned.configure")}</Button>
    </form>
  );
}

/** 027: which shelf a bought product sits on (the shop's own departments: theme packs apart from packs). */
function departmentKey(row: OwnershipRow, product: Product | undefined): string {
  return product ? departmentOfProduct(product) : departmentOf(row.product_type);
}

/**
 * ``/marketplace/owned`` (spec 015 T026, T028; 027 redesign): what I bought, at a glance — how much, what
 * waits for me (a form to fill), my requests, then my collection as a grid of the products' own art, by
 * department and searchable; refunds where still possible; the full history folded at the bottom.
 */
export default function OwnedPage() {
  const t = useT();
  const format = useFormat();
  const purchases = usePurchases();
  const products = useProducts({ category: "", q: "" });
  const { refund } = useOwnedActions();
  const [department, setDepartment] = useState("");
  const [query, setQuery] = useState("");
  const error = refund.error instanceof ApiError ? refund.error.code : null;
  const rows = purchases.data ?? [];
  const live = rows.filter((r) => ["active", "needs_configuration", "activation_failed"].includes(r.state));
  const todo = live.filter((r) => r.state === "needs_configuration");
  const collection = live.filter((r) => r.state !== "needs_configuration");
  const byKey = new Map((products.data ?? []).map((p) => [p.key, p]));
  const spent = rows
    .filter((r) => r.origin === "purchase" && !["refunded"].includes(r.state))
    .reduce((sum, r) => sum + r.price_paid, 0);
  const departments = DEPARTMENTS.filter((d) =>
    collection.some((r) => departmentOf(r.product_type) === d.key),
  );
  const shown = collection.filter(
    (r) =>
      (!department || departmentOf(r.product_type) === department) &&
      (!query.trim() || r.product_name.toLowerCase().includes(query.trim().toLowerCase())),
  );
  const columns: Column<OwnershipRow>[] = [
    {
      key: "product",
      header: t("marketplace:history.product"),
      render: (r) => r.product_name,
      rowHeader: true,
    },
    {
      key: "origin",
      header: t("marketplace:history.origin"),
      render: (r) => t(`marketplace:origin.${r.origin}`),
    },
    { key: "price", header: t("marketplace:history.price"), render: (r) => format.number(r.price_paid) },
    {
      key: "state",
      header: t("marketplace:history.state"),
      render: (r) => t(`marketplace:ownership.${r.state}`),
    },
    { key: "date", header: t("marketplace:history.date"), render: (r) => format.date(r.acquired_at) },
  ];
  return (
    <div className="owned ds-stack">
      <PageHeader
        icon="package"
        title={t("marketplace:owned.title")}
        context={t("marketplace:owned.context")}
      />
      {purchases.isError ? <FunctionalState state="unavailable" onRetry={() => purchases.refetch()} /> : null}
      {error ? (
        <p role="alert">{t(`marketplace:purchase.error.${error.split(".")[1] ?? "generic"}`)}</p>
      ) : null}

      <dl className="owned-stats">
        <div>
          <dt>{t("marketplace:owned.statOwned")}</dt>
          <dd>{format.number(collection.length)}</dd>
        </div>
        <div>
          <dt>{t("marketplace:owned.statSpent")}</dt>
          <dd>
            <Icon name="coins" size={18} /> {format.number(spent)}
          </dd>
        </div>
        <div>
          <dt>{t("marketplace:owned.statTodo")}</dt>
          <dd data-alert={todo.length || undefined}>{format.number(todo.length)}</dd>
        </div>
      </dl>

      {todo.length ? (
        <section aria-labelledby="owned-todo" className="ds-stack">
          <h2 id="owned-todo" className="owned__heading">
            <Icon name="sparkles" size={18} /> {t("marketplace:owned.todo")}
          </h2>
          {todo.map((row) => {
            const product = byKey.get(row.product_key);
            return (
              <article key={row.id} className="owned-todo">
                {product ? <ProductArt product={product} size="mini" /> : null}
                <div className="ds-stack">
                  <h3>{row.product_name}</h3>
                  <NeedsConfiguration row={row} />
                </div>
              </article>
            );
          })}
        </section>
      ) : null}

      <MyRequests />

      <section aria-labelledby="owned-collection" className="ds-stack">
        <div className="owned__bar">
          <h2 id="owned-collection" className="owned__heading">
            <Icon name="package" size={18} /> {t("marketplace:owned.collection")}
          </h2>
          <label className="shop-search owned__search">
            <Icon name="search" size={16} />
            <span className="visually-hidden">{t("marketplace:owned.search")}</span>
            <input
              type="search"
              value={query}
              placeholder={t("marketplace:owned.search")}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
        {departments.length > 1 ? (
          <fieldset className="owned__filters" aria-label={t("marketplace:shop.departments")}>
            <button type="button" aria-pressed={!department} onClick={() => setDepartment("")}>
              {t("marketplace:shop.allTypes")}
            </button>
            {departments.map((d) => (
              <button
                key={d.key}
                type="button"
                aria-pressed={department === d.key}
                onClick={() => setDepartment(department === d.key ? "" : d.key)}
              >
                <Icon name={d.icon} size={14} /> {t(`marketplace:department.${d.key}`)}
              </button>
            ))}
          </fieldset>
        ) : null}
        {shown.length ? (
          <ul className="owned-grid">
            {shown.map((row) => {
              const product = byKey.get(row.product_key);
              const refundable = row.refundable_until && new Date(row.refundable_until) > new Date();
              return (
                <li key={row.id} className="owned-item" data-rarity={product?.rarity ?? "common"}>
                  <a className="owned-item__art" href={`/marketplace/products/${row.product_key}`}>
                    {product ? (
                      <ProductArt product={product} size="card" />
                    ) : (
                      <Icon name="package" size={32} />
                    )}
                  </a>
                  <div className="owned-item__body">
                    <strong>{row.product_name}</strong>
                    <span className="owned-item__meta">
                      {t(`marketplace:department.${departmentKey(row, product)}`)} ·{" "}
                      {t(`marketplace:type.${row.product_type}`)}
                    </span>
                    <span className="owned-item__meta">
                      {row.origin === "purchase"
                        ? t("marketplace:owned.boughtOn", { date: format.date(row.acquired_at) })
                        : t("marketplace:owned.givenOn", { date: format.date(row.acquired_at) })}
                    </span>
                    {row.state === "activation_failed" ? (
                      <span className="owned-item__warn">
                        <Icon name="warning" size={14} /> {t("marketplace:ownership.activation_failed")}
                      </span>
                    ) : null}
                    {refundable ? (
                      <Button
                        variant="ghost"
                        onClick={() => refund.mutate({ id: row.id, reason: "Changed my mind" })}
                      >
                        <Icon name="sync" size={14} />
                        {t("marketplace:owned.refund", { date: format.date(row.refundable_until as string) })}
                      </Button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : purchases.isSuccess ? (
          <p className="owned__empty">
            {t(collection.length ? "marketplace:owned.none" : "marketplace:owned.empty")}
          </p>
        ) : null}
      </section>

      {rows.length ? (
        <details className="owned-history">
          <summary>
            <Icon name="list" size={16} /> {t("marketplace:history.title")} ({rows.length})
          </summary>
          <Table
            caption={t("marketplace:history.title")}
            columns={columns}
            rows={rows}
            rowKey={(r) => r.id}
          />
        </details>
      ) : null}
    </div>
  );
}
