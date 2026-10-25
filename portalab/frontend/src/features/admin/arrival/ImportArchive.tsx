import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Archive, type Inspected, percent, type Run, uploadArchive } from "../backup/api";
import { formatBytes } from "../ControlCenter";
import "../backup/backup.css";

/**
 * Issue 247 — the arrival wizard's import: an archive of another Portalab, sent from the browser or already
 * copied into the server's ``backups`` folder, opened with its passphrase and shown (whose portal, when,
 * how many members, services and packs) before it is brought in. Then its progress; once over, the portal is
 * restarted and its members sign in as before.
 */
export function ImportArchive({ language }: { language: string }) {
  const t = useT();
  const ids = { file: useId(), server: useId(), phrase: useId() };
  const [name, setName] = useState("");
  const [sent, setSent] = useState<number | null>(null);
  const [passphrase, setPassphrase] = useState("");
  const [inspected, setInspected] = useState<Inspected | null>(null);
  const [started, setStarted] = useState(false);
  const server = useQuery({
    queryKey: ["arrival", "archives"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/first-run/import")).data as unknown as { archives: Archive[] }).archives,
  });
  const upload = useMutation({
    mutationFn: (file: File) => uploadArchive(file, setSent),
    onSuccess: (received) => {
      setName(received);
      setInspected(null);
      void server.refetch();
    },
  });
  const inspect = useMutation({
    mutationFn: async () =>
      (await api.POST("/api/v1/admin/first-run/import/inspect", { body: { name, passphrase } }))
        .data as unknown as Inspected,
    onSuccess: setInspected,
  });
  const start = useMutation({
    mutationFn: async () => api.POST("/api/v1/admin/first-run/import", { body: { name, passphrase } }),
    onSuccess: () => setStarted(true),
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

  if (run && run.state === "done") {
    return (
      <div className="arrival-import" role="status">
        <h3>
          <Icon name="check" size={18} /> {t("account:arrival.import.done")}
        </h3>
        <p>{t("account:arrival.import.restart")}</p>
        <p>
          <a className="ds-button ds-button--primary" href="/">
            {t("account:arrival.signIn")}
          </a>
        </p>
      </div>
    );
  }
  if (started) {
    return (
      <div className="arrival-import">
        {run && run.state === "failed" ? (
          <p role="alert">
            {t(`account:arrival.import.error.${(run.error?.code ?? "backup.failed").replace("backup.", "")}`)}
          </p>
        ) : (
          <div className="backup-run" role="status">
            <span className="backup-run__label">
              {t(`account:arrival.import.phase.${run?.phase ?? "starting"}`)} — {run ? percent(run) : 0} %
            </span>
            <progress
              max={100}
              value={run ? percent(run) : 0}
              aria-label={t("account:arrival.import.progress")}
            />
          </div>
        )}
      </div>
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
          const file = e.target.files?.[0];
          if (file) upload.mutate(file);
        }}
      />
      {upload.isPending && sent !== null ? (
        <progress max={1} value={sent} aria-label={t("account:arrival.import.sending")} />
      ) : null}
      {upload.isError ? <p role="alert">{t("account:arrival.import.sendFailed")}</p> : null}
      {server.data?.length ? (
        <>
          <label htmlFor={ids.server}>{t("account:arrival.import.server")}</label>
          <select
            id={ids.server}
            value={name}
            onChange={(e) => (setName(e.target.value), setInspected(null))}
          >
            <option value="">—</option>
            {server.data.map((a) => (
              <option key={a.name} value={a.name}>
                {a.name} ({formatBytes(a.bytes, language)})
              </option>
            ))}
          </select>
        </>
      ) : (
        <p className="field-hint">{t("account:arrival.import.serverHint")}</p>
      )}
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
          {inspected.compatible ? (
            <>
              <p className="arrival__lead">{t("account:arrival.import.warning")}</p>
              <Button onClick={() => start.mutate()} disabled={start.isPending} aria-busy={start.isPending}>
                <Icon name="download" size={16} />
                {t("account:arrival.import.start")}
              </Button>
              {start.isError ? <p role="alert">{error(start.error)}</p> : null}
            </>
          ) : (
            <p role="alert">{t("account:arrival.import.error.version")}</p>
          )}
        </div>
      ) : null}
    </form>
  );
}
