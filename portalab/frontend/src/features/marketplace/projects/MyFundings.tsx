import { Link } from "react-router";
import { type Column, Table } from "../../../design-system/components/Layout";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type ProjectFunding, useMyFundings } from "../api";

/** My fundings (spec 015 T014): what I reserved, what was consumed or released, per project. */
export function MyFundings() {
  const t = useT();
  const format = useFormat();
  const fundings = useMyFundings();
  const columns: Column<ProjectFunding>[] = [
    {
      key: "project",
      header: t("marketplace:fundings.project"),
      render: (row) => <Link to={`/projects/${row.project_id}`}>{row.project_title}</Link>,
      rowHeader: true,
    },
    {
      key: "state",
      header: t("marketplace:fundings.state"),
      render: (row) => t(`marketplace:state.${row.project_state}`),
    },
    { key: "amount", header: t("marketplace:fundings.amount"), render: (row) => format.number(row.amount) },
    {
      key: "status",
      header: t("marketplace:fundings.status"),
      render: (row) =>
        t("marketplace:fundings.split", {
          reserved: format.number(row.reserved),
          consumed: format.number(row.consumed),
          released: format.number(row.released),
        }),
    },
  ];
  return (
    <section aria-labelledby="my-fundings" className="ds-stack">
      <h2 id="my-fundings">{t("marketplace:fundings.title")}</h2>
      {fundings.isError ? <FunctionalState state="unavailable" onRetry={() => fundings.refetch()} /> : null}
      {fundings.data?.length === 0 ? <p>{t("marketplace:fundings.empty")}</p> : null}
      {fundings.data?.length ? (
        <Table
          caption={t("marketplace:fundings.title")}
          columns={columns}
          rows={fundings.data}
          rowKey={(r) => r.id}
        />
      ) : null}
    </section>
  );
}
