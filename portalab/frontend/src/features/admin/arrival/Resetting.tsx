import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { useT } from "../../../i18n/hooks/useT";
import { I18nProvider } from "../../../i18n/provider/I18nProvider";
import type { Run } from "../backup/api";
import { Launch, type LaunchTask } from "./Launch";
import { Stage } from "./Stage";
import "../backup/backup.css";
import "./arrival.css";

/**
 * Issue 247 — the portal being reset, followed outside the shell (the session went with the database): every
 * step as the server tells it — each data folder emptied (the visual packs, the files sent, the cards…), each
 * module's data dropped, a new database, its permissions, Portalab's own packs written again — then the
 * restart to do; the arrival wizard is what the portal shows next.
 */
type Reset = Run & { steps?: string[]; on?: string | null };

const STEPS = ["schema.drop", "schema.create", "schema.permissions", "schema.packs"]; // before the server tells

export function resetTasks(
  run: Reset | null | undefined,
  over: boolean,
  failed: boolean,
  t: (id: string, values?: Record<string, string | number>) => string,
): { tasks: LaunchTask[]; percent: number } {
  const steps = run?.steps?.length ? run.steps : STEPS;
  const at = over ? steps.length : Math.max(0, steps.indexOf(run?.phase ?? ""));
  const share = run && run.total > 0 ? Math.min(1, run.done / run.total) : 0;
  const tasks = steps.map((key, index): LaunchTask => {
    const id = `account:reset.phase.${key}`;
    const known = t(id);
    const unknownFolder = key.startsWith("files.") && known === id.slice("account:".length);
    const label = unknownFolder ? t("account:reset.phase.files.other", { name: key.slice(6) }) : known;
    const running = index === at && !over;
    return {
      key,
      label,
      detail:
        running && run?.on ? (run.total > 0 ? `${run.on} (${run.done + 1}/${run.total})` : run.on) : null,
      state: index < at ? "done" : running ? (failed ? "failed" : "running") : "waiting",
    };
  });
  return { tasks, percent: over ? 100 : Math.round(((at + share) / steps.length) * 100) };
}

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
  const { tasks, percent } = resetTasks(run as Reset | null | undefined, over, failed, t);
  return (
    <Stage steps={[]}>
      <section className="arrival-card arrival-card--launch" aria-label={t("account:reset.title")}>
        <Launch
          title={t(over ? "account:reset.done" : "account:reset.title")}
          tasks={tasks}
          percent={percent}
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
