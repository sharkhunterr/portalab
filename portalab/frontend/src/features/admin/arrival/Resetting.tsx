import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { I18nProvider } from "../../../i18n/provider/I18nProvider";
import { percent, type Run } from "../backup/api";
import "../backup/backup.css";
import "./arrival.css";

/**
 * Issue 247 — the portal being reset, followed outside the shell (the session went with the database): its
 * progress, then the restart to do; the arrival wizard is what the portal shows next.
 */
function Progress() {
  const t = useT();
  const status = useQuery({
    queryKey: ["arrival", "reset-status"],
    retry: false,
    refetchInterval: (query) => (query.state.data?.state === "running" ? 1500 : false),
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/first-run/import/status")).data as unknown as { run: Run | null }).run,
  });
  const run = status.data;
  return (
    <main className="arrival">
      <header className="arrival__brand">
        <span className="ds-auth__mark" aria-hidden="true">
          <Icon name="sync" size={26} />
        </span>
        <div>
          <h1>{t("account:reset.title")}</h1>
        </div>
      </header>
      <section className="arrival__panel">
        {run?.state === "failed" ? (
          <p role="alert">{t("account:reset.failed")}</p>
        ) : run?.state === "done" || (status.isFetched && !run) ? (
          <div role="status">
            <h2>
              <Icon name="check" size={18} /> {t("account:reset.done")}
            </h2>
            <p>{t("account:reset.restart")}</p>
            <p>
              <a className="ds-button ds-button--primary" href="/">
                {t("account:reset.open")}
              </a>
            </p>
          </div>
        ) : (
          <div className="backup-run" role="status">
            <span className="backup-run__label">
              {t(`account:reset.phase.${run?.phase ?? "starting"}`)} — {run ? percent(run) : 0} %
            </span>
            <progress max={100} value={run ? percent(run) : 0} aria-label={t("account:reset.title")} />
          </div>
        )}
      </section>
    </main>
  );
}

export function Resetting() {
  const language = (globalThis.navigator?.language ?? "en").slice(0, 2);
  return (
    <I18nProvider anonymous namespaces={["core", "account"]} override={{ language, locale: language }}>
      <Progress />
    </I18nProvider>
  );
}
