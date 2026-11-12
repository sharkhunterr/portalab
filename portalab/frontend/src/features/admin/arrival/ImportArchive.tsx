import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Inspected, percent, type Run, uploadArchive } from "../backup/api";
import { formatBytes } from "../ControlCenter";
import { holdArrival } from "./hold";
import { ImportBlocks } from "./ImportBlocks";
import { requested } from "./importBlocks";
import { Launch } from "./Launch";
import "../backup/backup.css";

const IMPORT_PHASES = ["reading", "schema", "tables", "selection", "upgrade", "files"] as const;
const UPGRADE_ONLY = new Set<string>(["schema", "upgrade"]); // an archive of an older Portalab
const PARTIAL_ONLY = new Set<string>(["selection"]); // issue 392: some blocks only
const IMPORT_SLIDES: ReadonlyArray<readonly [icon: string, key: string]> = [
  ["users", "members"],
  ["server", "services"],
  ["shield", "secrets"],
  ["sparkles", "after"],
];

/**
 * Issue 247 — the arrival wizard's import: an archive of another Portalab, sent from the browser (that is
 * all: the file, then its passphrase), opened and shown (whose portal, when, how many members, services and
 * packs) before it is brought in. Then its progress; once over, the portal is
 * restarted and its members sign in as before.
 */
export function ImportArchive({ language }: { language: string }) {
  const t = useT();
  const ids = { file: useId(), phrase: useId() };
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sent, setSent] = useState<number | null>(null);
  const [passphrase, setPassphrase] = useState("");
  const [inspected, setInspected] = useState<Inspected | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [started, setStarted] = useState(false);
  const upload = useMutation({
    mutationFn: (file: File) => uploadArchive(file, setSent),
    onSuccess: (received) => {
      setName(received);
      setInspected(null);
    },
  });
  const inspect = useMutation({
    mutationFn: async () =>
      (await api.POST("/api/v1/admin/first-run/import/inspect", { body: { name, passphrase } }))
        .data as unknown as Inspected,
    onSuccess: (found) => {
      setInspected(found);
      setChosen(new Set(found.blocks.map((b) => b.key))); // everything, until something is unticked
    },
  });
  const blocks = inspected ? requested(inspected.blocks, chosen) : undefined;
  const start = useMutation({
    mutationFn: async () =>
      api.POST("/api/v1/admin/first-run/import", { body: { name, passphrase, blocks: blocks ?? null } }),
    onSuccess: () => {
      holdArrival(true); // issue 249: the portal set up at the end, the wizard stays until then
      setStarted(true);
    },
  });
  const status = useQuery({
    queryKey: ["arrival", "import-status"],
    enabled: started,
    refetchInterval: (query) => (query.state.data?.state === "running" || !query.state.data ? 1500 : false),
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/first-run/import/status")).data as unknown as { run: Run | null }).run,
  });
  const run = status.data;
  const error = (e: unknown) =>
    e instanceof ApiError && e.code
      ? t(`account:arrival.import.error.${e.code.replace("backup.", "")}`)
      : t("account:arrival.error");

  if (started) {
    const phases = IMPORT_PHASES.filter(
      (p) =>
        (inspected?.compatibility === "older" || !UPGRADE_ONLY.has(p)) &&
        (blocks !== undefined || !PARTIAL_ONLY.has(p)),
    );
    const at =
      run?.state === "done"
        ? phases.length
        : phases.indexOf((run?.phase ?? "reading") as (typeof phases)[number]);
    const failed = run?.state === "failed";
    return (
      <Launch
        title={t(run?.state === "done" ? "account:arrival.import.done" : "account:arrival.import.running")}
        lead={inspected ? t("account:arrival.import.from", { site: inspected.site }) : undefined}
        tasks={phases.map((phase, index) => ({
          key: phase,
          label: t(`account:arrival.import.phase.${phase}`),
          state:
            index < at
              ? "done"
              : index === at || (at < 0 && index === 0)
                ? failed
                  ? "failed"
                  : "running"
                : "waiting",
        }))}
        percent={run ? percent(run) : 0}
        slides={IMPORT_SLIDES.map(([icon, key]) => ({
          icon,
          title: t(`account:arrival.import.slide.${key}.title`),
          text: t(`account:arrival.import.slide.${key}.text`),
        }))}
        failed={failed}
        done={run?.state === "done"}
      >
        {failed ? (
          <p role="alert">
            {t(
              `account:arrival.import.error.${(run?.error?.code ?? "backup.failed").replace("backup.", "")}`,
            )}
          </p>
        ) : run?.state === "done" ? (
          <div className="launch__error" role="status">
            <p>{t("account:arrival.import.restart")}</p>
            <p>
              <a className="ds-button ds-button--primary" href="/">
                {t("account:arrival.signIn")}
              </a>
            </p>
          </div>
        ) : null}
      </Launch>
    );
  }
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (name && passphrase) inspect.mutate();
  };
  return (
    <form className="arrival-import arrival__form" onSubmit={submit}>
      <label htmlFor={ids.file}>{t("account:arrival.import.file")}</label>
      <input
        id={ids.file}
        type="file"
        accept=".plbackup"
        disabled={upload.isPending}
        onChange={(e) => {
          const chosen = e.target.files?.[0];
          if (chosen) {
            setFile(chosen);
            setName("");
            upload.mutate(chosen);
          }
        }}
      />
      {upload.isPending && sent !== null ? (
        <progress max={1} value={sent} aria-label={t("account:arrival.import.sending")} />
      ) : null}
      {upload.isError ? <p role="alert">{t("account:arrival.import.sendFailed")}</p> : null}
      {name && file ? (
        <p role="status" className="arrival-import__sent">
          <Icon name="check" size={16} />
          {t("account:arrival.import.sent", { name: file.name, size: formatBytes(file.size, language) })}
        </p>
      ) : null}
      <label htmlFor={ids.phrase}>{t("account:arrival.import.passphrase")}</label>
      <input
        id={ids.phrase}
        type="password"
        autoComplete="off"
        value={passphrase}
        onChange={(e) => (setPassphrase(e.target.value), setInspected(null))}
      />
      <Button type="submit" variant="secondary" disabled={!name || !passphrase || inspect.isPending}>
        <Icon name="search" size={16} />
        {t("account:arrival.import.check")}
      </Button>
      {inspect.isError ? <p role="alert">{error(inspect.error)}</p> : null}
      {inspected ? (
        <div className="arrival-import__summary">
          <dl className="arrival__recap">
            <div>
              <dt>{t("account:arrival.import.portal")}</dt>
              <dd>{inspected.site}</dd>
            </div>
            <div>
              <dt>{t("account:arrival.import.version")}</dt>
              <dd>Portalab {inspected.portalab}</dd>
            </div>
            <div>
              <dt>{t("account:arrival.import.saved")}</dt>
              <dd>{new Date(inspected.created_at).toLocaleString(language)}</dd>
            </div>
            <div>
              <dt>{t("account:arrival.import.holds")}</dt>
              <dd>
                {t("account:arrival.import.counts", {
                  members: inspected.counts.members ?? 0,
                  services: inspected.counts.services ?? 0,
                  packs: inspected.counts.packs ?? 0,
                })}
              </dd>
            </div>
            <div>
              <dt>{t("account:arrival.import.files")}</dt>
              <dd>
                {formatBytes(
                  inspected.folders.reduce((sum, f) => sum + f.bytes, 0),
                  language,
                )}
                {inspected.options.media ? "" : ` · ${t("account:arrival.import.noMedia")}`}
              </dd>
            </div>
          </dl>
          {inspected.compatibility === "older" ? (
            <p className="arrival__lead">
              {t("account:arrival.import.older", { version: inspected.portalab })}
            </p>
          ) : null}
          {inspected.compatible ? (
            <>
              <ImportBlocks
                blocks={inspected.blocks}
                chosen={chosen}
                onChange={setChosen}
                disabled={start.isPending}
              />
              <p className="arrival__lead">
                {t(
                  blocks === undefined
                    ? "account:arrival.import.warning"
                    : "account:arrival.import.warningPartial",
                )}
              </p>
              <Button onClick={() => start.mutate()} disabled={start.isPending} aria-busy={start.isPending}>
                <Icon name="download" size={16} />
                {t("account:arrival.import.start")}
              </Button>
              {start.isError ? <p role="alert">{error(start.error)}</p> : null}
            </>
          ) : (
            <p role="alert">{t("account:arrival.import.error.newer", { version: inspected.portalab })}</p>
          )}
        </div>
      ) : null}
    </form>
  );
}
