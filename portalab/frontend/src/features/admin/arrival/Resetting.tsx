import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { useT } from "../../../i18n/hooks/useT";
import { I18nProvider } from "../../../i18n/provider/I18nProvider";
import { percent, type Run } from "../backup/api";
import { Launch } from "./Launch";
import { Stage } from "./Stage";
import "../backup/backup.css";

const PHASES = ["schema", "files"] as const;

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
  const over = run?.state === "done" || (status.isFetched && !run);
  const failed = run?.state === "failed";
  const at = over ? PHASES.length : PHASES.indexOf((run?.phase ?? "schema") as (typeof PHASES)[number]);
  return (
    <Stage steps={[]}>
      <section className="arrival-card arrival-card--launch" aria-label={t("account:reset.title")}>
        <Launch
          title={t(over ? "account:reset.done" : "account:reset.title")}
          tasks={PHASES.map((phase, index) => ({
            key: phase,
            label: t(`account:reset.phase.${phase}`),
            state: index < at ? "done" : index === at ? (failed ? "failed" : "running") : "waiting",
          }))}
          percent={run ? percent(run) : 0}
          slides={[
            {
              icon: "database",
              title: t("account:reset.slide.kept.title"),
              text: t("account:reset.slide.kept.text"),
            },
            {
              icon: "rocket",
              title: t("account:reset.slide.next.title"),
              text: t("account:reset.slide.next.text"),
            },
          ]}
          failed={failed}
          done={over}
        >
          {failed ? (
            <p role="alert">{t("account:reset.failed")}</p>
          ) : over ? (
            <div className="launch__error" role="status">
              <p>{t("account:reset.restart")}</p>
              <p>
                <a className="ds-button ds-button--primary" href="/">
                  {t("account:reset.open")}
                </a>
              </p>
            </div>
          ) : null}
        </Launch>
      </section>
    </Stage>
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
