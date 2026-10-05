import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { type Column, Table } from "../../../design-system/components/Layout";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type OwnershipRow, useOwnedActions, usePurchases } from "../api";
import "../marketplace.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

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

/** ``/marketplace/owned`` (spec 015 T026, T028): what I own, its state, configuration, refunds, history. */
export default function OwnedPage() {
  const t = useT();
  const format = useFormat();
  const purchases = usePurchases();
  const { refund } = useOwnedActions();
  const error = refund.error instanceof ApiError ? refund.error.code : null;
  const live = (purchases.data ?? []).filter((r) =>
    ["active", "needs_configuration", "activation_failed"].includes(r.state),
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
    <div className="ds-stack">
      <PageHeader icon="shop" title={t("marketplace:owned.title")} />
      {purchases.isError ? <FunctionalState state="unavailable" onRetry={() => purchases.refetch()} /> : null}
      {error ? (
        <p role="alert">{t(`marketplace:purchase.error.${error.split(".")[1] ?? "generic"}`)}</p>
      ) : null}
      <ul className="ds-stack">
        {live.map((row) => (
          <li key={row.id} className="ds-card ds-stack">
            <h2>{row.product_name}</h2>
            <FunctionalState
              state={
                row.state === "active"
                  ? "available"
                  : row.state === "needs_configuration"
                    ? "partial"
                    : "error"
              }
              label={t(`marketplace:ownership.${row.state}`)}
            />
            {row.state === "needs_configuration" ? <NeedsConfiguration row={row} /> : null}
            {row.refundable_until && new Date(row.refundable_until) > new Date() ? (
              <Button
                variant="secondary"
                onClick={() => refund.mutate({ id: row.id, reason: "Changed my mind" })}
              >
                {t("marketplace:owned.refund", { date: format.date(row.refundable_until) })}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {live.length === 0 && purchases.isSuccess ? <p>{t("marketplace:owned.empty")}</p> : null}
      <section aria-labelledby="marketplace-history" className="ds-stack">
        <h2 id="marketplace-history">{t("marketplace:history.title")}</h2>
        {(purchases.data ?? []).length ? (
          <Table
            caption={t("marketplace:history.title")}
            columns={columns}
            rows={purchases.data ?? []}
            rowKey={(r) => r.id}
          />
        ) : null}
      </section>
    </div>
  );
}
