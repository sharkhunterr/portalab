import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { AdminPage, AdminSection, AdminTable } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useSite } from "../../../shell/site/site";
import { ApiError } from "../../../state/regions";
import "./backup.css";

/**
 * Issue 247 — which Portalab this is (its version, its archives' layout, each module's schema, the database)
 * and, at the bottom, starting again from scratch: everything erased but the backups, after typing the
 * portal's name and the password; the portal then restarts on its arrival wizard (``/resetting`` follows it,
 * outside the shell — the session goes with the database).
 */
interface Version {
  portalab: string;
  archive_format: number;
  python: string;
  database: string;
  started_at: string;
  schema: { module: string; revision: string }[];
}

function Reset() {
  const t = useT();
  const site = useSite();
  const [confirm, setConfirm] = useState("");
  const [password, setPassword] = useState("");
  const reset = useMutation({
    mutationFn: async () => api.POST("/api/v1/admin/system/reset", { body: { confirm, password } as never }),
    onSuccess: () => globalThis.location.assign("/resetting"),
  });
  const matches = confirm.trim().toLowerCase() === site.name.trim().toLowerCase();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (matches && password) reset.mutate();
  };
  return (
    <form onSubmit={submit} className="system-reset">
      <p>{t("admin:system.reset.lead")}</p>
      <ul className="system-reset__list">
        <li>{t("admin:system.reset.erased")}</li>
        <li>{t("admin:system.reset.kept")}</li>
        <li>{t("admin:system.reset.after")}</li>
      </ul>
      <p>
        <Link to="/admin/backups" className="ds-button ds-button--secondary">
          <Icon name="database" size={16} />
          {t("admin:system.reset.backupFirst")}
        </Link>
      </p>
      <TextField
        label={t("admin:system.reset.confirm", { name: site.name })}
        autoComplete="off"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
      />
      <TextField
        label={t("admin:system.reset.password")}
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {reset.isError ? (
        <p role="alert" className="services-admin__ko">
          {reset.error instanceof ApiError ? reset.error.message : t("admin:system.reset.failed")}
        </p>
      ) : null}
      <Button type="submit" variant="danger" disabled={!matches || !password || reset.isPending}>
        <Icon name="trash" size={16} />
        {t("admin:system.reset.go")}
      </Button>
    </form>
  );
}

export function SystemVersion() {
  const t = useT();
  const format = useFormat();
  const version = useQuery({
    queryKey: ["admin", "system", "version"],
    queryFn: async () => (await api.GET("/api/v1/admin/system/version")).data as unknown as Version,
  });
  const v = version.data;
  return (
    <AdminPage icon="info" title={t("admin:system.title")} description={t("admin:system.subtitle")}>
      <AdminSection title="Portalab" icon="sparkles">
        {v ? (
          <dl className="system-facts">
            <div>
              <dt>{t("admin:system.version")}</dt>
              <dd>
                <strong>{v.portalab}</strong>
              </dd>
            </div>
            <div>
              <dt>{t("admin:system.archive")}</dt>
              <dd>{t("admin:system.archiveFormat", { format: v.archive_format })}</dd>
            </div>
            <div>
              <dt>{t("admin:system.database")}</dt>
              <dd>{v.database}</dd>
            </div>
            <div>
              <dt>Python</dt>
              <dd>{v.python}</dd>
            </div>
            <div>
              <dt>{t("admin:system.started")}</dt>
              <dd>{format.dateTime(v.started_at)}</dd>
            </div>
          </dl>
        ) : null}
      </AdminSection>
      <AdminSection
        title={t("admin:system.schema")}
        description={t("admin:system.schemaHint")}
        icon="layers"
        flush
      >
        <details className="system-schema">
          <summary>{t("admin:system.schemaShow", { count: v?.schema.length ?? 0 })}</summary>
          <AdminTable
            label={t("admin:system.schema")}
            rows={v?.schema ?? []}
            rowKey={(row) => row.revision}
            columns={[
              { key: "module", header: t("admin:system.module"), primary: true, render: (row) => row.module },
              {
                key: "revision",
                header: t("admin:system.revision"),
                render: (row) => <code>{row.revision}</code>,
              },
            ]}
          />
        </details>
      </AdminSection>
      <AdminSection title={t("admin:system.reset.title")} icon="alert">
        <Reset />
      </AdminSection>
    </AdminPage>
  );
}

export default SystemVersion;
