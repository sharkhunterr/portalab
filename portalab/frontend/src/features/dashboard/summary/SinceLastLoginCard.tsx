import { useQueryClient } from "@tanstack/react-query";
import { useId } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useSummary } from "../api";

/** "Since your last visit" (spec 009 T028): permission-scoped changes; acknowledging advances the boundary. */
export function SinceLastLoginCard() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const client = useQueryClient();
  const summary = useSummary();
  async function seen() {
    await api.POST("/api/v1/dashboard/since-last-login/seen", { body: {} });
    await client.invalidateQueries({ queryKey: ["dashboard", "summary"] });
  }
  return (
    <section aria-labelledby={headingId} className="dashboard-summary ds-panel">
      <h2 id={headingId} className="dashboard-summary__title">
        <span className="dashboard-summary__icon" aria-hidden="true">
          <Icon name="sparkles" size={18} />
        </span>
        {t("dashboard:summary.title")}
      </h2>
      {summary.isPending ? <FunctionalState state="loading" /> : null}
      {summary.isError ? <FunctionalState state="error" onRetry={() => summary.refetch()} /> : null}
      {summary.data && summary.data.items.length === 0 ? (
        <div className="dashboard-summary__empty">
          <p>{t("dashboard:summary.empty")}</p>
          <Link className="ds-button ds-button--secondary" to="/services">
            {t("dashboard:summary.browse")}
          </Link>
        </div>
      ) : null}
      {summary.data?.items.length ? (
        <>
          <ul className="widget-list">
            {summary.data.items.map((item) => (
              <li key={`${item.kind}:${item.ref}:${item.occurred_at}`}>
                <Link to={item.ref.startsWith("/") ? item.ref : "/"}>
                  {item.title ??
                    (item.title_key
                      ? t(item.title_key, item.title_args as Record<string, string>)
                      : item.ref)}
                </Link>{" "}
                <span className="widget__meta">{format.dateTime(item.occurred_at)}</span>
              </li>
            ))}
          </ul>
          <Button variant="secondary" onClick={seen}>
            {t("dashboard:summary.seen")}
          </Button>
        </>
      ) : null}
      {summary.data?.unavailable.length ? (
        <p className="widget__meta">{t("dashboard:summary.unavailable")}</p>
      ) : null}
    </section>
  );
}
