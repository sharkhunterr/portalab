import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../../api/client";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminTable,
  FormActions,
  FormGrid,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { ApiError } from "../../../state/regions";
import { formatBytes } from "../ControlCenter";
import { type Archive, BACKUPS_KEY, percent, type Run, useBackups } from "./api";
import "./backup.css";

/**
 * Issue 247 — the portal's backups: one archive holding the members, the settings, the services (their
 * secrets readable again only with the passphrase), the content, play and the media history, the files and,
 * on request, the media images and the technical history. Saved here (in the background, the portal keeps
 * answering), downloaded, and brought into a new installation by its arrival wizard.
 */
export function RunProgress({ run }: { run: Run }) {
  const t = useT();
  const value = percent(run);
  return (
    <div className="backup-run" role="status">
      <span className="backup-run__label">
        {t(`admin:backup.phase.${run.phase}`)} — {value} %
      </span>
      <progress max={100} value={value} aria-label={t(`admin:backup.phase.${run.phase}`)} />
    </div>
  );
}

function CreateForm({ running }: { running: boolean }) {
  const t = useT();
  const client = useQueryClient();
  const [passphrase, setPassphrase] = useState("");
  const [confirm, setConfirm] = useState("");
  const [media, setMedia] = useState(true);
  const [history, setHistory] = useState(false);
  const create = useMutation({
    mutationFn: async () =>
      api.POST("/api/v1/admin/backups", { body: { passphrase, media, history } as never }),
    onSuccess: () => {
      setPassphrase("");
      setConfirm("");
      void client.invalidateQueries({ queryKey: BACKUPS_KEY });
    },
  });
  const mismatch = confirm.length > 0 && confirm !== passphrase;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!mismatch) create.mutate();
  };
  return (
    <form onSubmit={submit}>
      <FormGrid>
        <TextField
          label={t("admin:backup.passphrase")}
          hint={t("admin:backup.passphraseHint")}
          type="password"
          autoComplete="new-password"
          minLength={12}
          required
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
        />
        <TextField
          label={t("admin:backup.confirm")}
          type="password"
          autoComplete="new-password"
          required
          error={mismatch ? t("admin:backup.mismatch") : undefined}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </FormGrid>
      <CheckboxField
        label={t("admin:backup.media")}
        hint={t("admin:backup.mediaHint")}
        checked={media}
        onChange={(e) => setMedia(e.target.checked)}
      />
      <CheckboxField
        label={t("admin:backup.history")}
        hint={t("admin:backup.historyHint")}
        checked={history}
        onChange={(e) => setHistory(e.target.checked)}
      />
      {create.isError ? (
        <p role="alert" className="services-admin__ko">
          {create.error instanceof ApiError ? create.error.message : t("admin:backup.failed")}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={running || create.isPending || mismatch} aria-busy={create.isPending}>
          <Icon name="database" size={16} />
          {t("admin:backup.create")}
        </Button>
      </FormActions>
    </form>
  );
}

function Archives({ archives }: { archives: Archive[] }) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const client = useQueryClient();
  const remove = useMutation({
    mutationFn: async (name: string) =>
      api.DELETE("/api/v1/admin/backups/{name}", { params: { path: { name } } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: BACKUPS_KEY }),
  });
  if (!archives.length) return <AdminEmpty icon="database" title={t("admin:backup.none")} />;
  return (
    <AdminTable<Archive>
      label={t("admin:backup.archives")}
      rows={archives}
      rowKey={(a) => a.name}
      columns={[
        { key: "name", header: t("admin:backup.name"), primary: true, render: (a) => <code>{a.name}</code> },
        { key: "date", header: t("admin:backup.date"), render: (a) => format.dateTime(a.modified_at) },
        { key: "size", header: t("admin:backup.size"), render: (a) => formatBytes(a.bytes, locale) },
        {
          key: "actions",
          header: t("admin:backup.actions"),
          render: (a) => (
            <span className="backup-actions">
              <a
                className="ds-button ds-button--secondary"
                href={`/api/v1/admin/backups/${encodeURIComponent(a.name)}/download`}
                download={a.name}
              >
                <Icon name="download" size={16} />
                {t("admin:backup.download")}
              </a>
              <Button
                variant="ghost"
                disabled={remove.isPending}
                onClick={() => {
                  if (globalThis.confirm(t("admin:backup.deleteConfirm", { name: a.name })))
                    remove.mutate(a.name);
                }}
                aria-label={`${t("admin:backup.delete")} ${a.name}`}
              >
                <Icon name="trash" size={16} />
              </Button>
            </span>
          ),
        },
      ]}
    />
  );
}

export function BackupsAdmin() {
  const t = useT();
  const backups = useBackups();
  const run = backups.data?.run ?? null;
  const running = run?.state === "running";
  return (
    <AdminPage icon="database" title={t("admin:backup.title")} description={t("admin:backup.subtitle")}>
      <AdminSection title={t("admin:backup.new")} icon="database" description={t("admin:backup.newHint")}>
        {running && run ? <RunProgress run={run} /> : <CreateForm running={running} />}
        {run && run.kind === "create" && run.state === "done" ? (
          <p role="status" className="services-admin__ok">
            <StatusBadge tone="ok">{t("admin:backup.done")}</StatusBadge>{" "}
            <code>{String(run.result.name)}</code>
          </p>
        ) : null}
        {run && run.state === "failed" ? (
          <p role="alert" className="services-admin__ko">
            {t("admin:backup.failed")} ({run.error?.code})
          </p>
        ) : null}
      </AdminSection>
      <AdminSection title={t("admin:backup.archives")} icon="folder" flush>
        <Archives archives={backups.data?.archives ?? []} />
      </AdminSection>
      <AdminSection title={t("admin:backup.restoreTitle")} icon="rocket">
        <p className="admin-muted">{t("admin:backup.restoreHint")}</p>
      </AdminSection>
    </AdminPage>
  );
}

export default BackupsAdmin;
