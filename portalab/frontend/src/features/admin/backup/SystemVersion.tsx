import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { AdminPage, AdminSection, AdminTable, StatusBadge } from "../../../design-system/admin/AdminKit";
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
interface Update {
  enabled: boolean;
  current: string;
  latest?: string | null;
  update_available?: boolean;
  url?: string;
  published_at?: string | null;
  checked_at?: string | null;
  error?: string | null;
}

interface Posture {
  key: string;
  level: "ok" | "warn" | "info";
  values: Record<string, string | number | boolean | null>;
  setting: string | null;
}

interface Version {
  portalab: string;
  build?: { commit: string | null; date: string | null };
  update?: Update;
  security?: Posture[];
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

const VERSION_KEY = ["admin", "system", "version"];

/** Issue 410: whether a newer Portalab is released on GitHub — and asking again now. */
function UpdateStatus({ update }: { update: Update }) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const check = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/admin/system/version/check")).data as unknown as Update,
    onSuccess: (fresh) =>
      client.setQueryData<Version>(VERSION_KEY, (old) => (old ? { ...old, update: fresh } : old)),
  });
  if (!update.enabled) {
    return (
      <span className="system-update">
        <StatusBadge tone="neutral">{t("admin:system.update.off")}</StatusBadge>
        <Link to="/admin/configuration?q=admin.updateCheck">{t("admin:system.update.turnOn")}</Link>
      </span>
    );
  }
  const badge = update.update_available ? (
    <StatusBadge tone="warn">
      {t("admin:system.update.available", { version: update.latest ?? "" })}
    </StatusBadge>
  ) : update.latest ? (
    <StatusBadge tone="ok">{t("admin:system.update.upToDate")}</StatusBadge>
  ) : update.error ? (
    <StatusBadge tone="neutral">{t("admin:system.update.failed")}</StatusBadge>
  ) : (
    <StatusBadge tone="neutral">{t("admin:system.update.none")}</StatusBadge>
  );
  return (
    <span className="system-update">
      {badge}
      {update.update_available && update.url ? (
        <a href={update.url} target="_blank" rel="noopener noreferrer">
          {t("admin:system.update.notes")}
          <Icon name="external" size={14} />
        </a>
      ) : null}
      <Button
        variant="ghost"
        onClick={() => check.mutate()}
        disabled={check.isPending}
        aria-busy={check.isPending}
      >
        <Icon name="sync" size={14} />
        {t("admin:system.update.check")}
      </Button>
      {update.checked_at ? (
        <small className="system-update__when">
          {t("admin:system.update.checked", { when: format.dateTime(update.checked_at) })}
        </small>
      ) : null}
    </span>
  );
}

/** The posture's values as message parameters (a missing number reads « null » in a select). */
function params(values: Posture["values"]): Record<string, string | number> {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, typeof value === "number" ? value : String(value)]),
  );
}

/** Issue 410: the portal's security posture — each point says what it is and what to do. */
function SecurityPosture({ points }: { points: Posture[] }) {
  const t = useT();
  return (
    <ul className="system-posture">
      {points.map((point) => (
        <li key={point.key} className={`system-posture__item system-posture__item--${point.level}`}>
          <Icon name={point.level === "warn" ? "alert" : point.level === "ok" ? "check" : "info"} size={18} />
          <div>
            <strong>{t(`admin:system.security.${point.key}.${point.level}`, params(point.values))}</strong>
            {point.level !== "ok" ? (
              <p>{t(`admin:system.security.${point.key}.hint`, params(point.values))}</p>
            ) : null}
            {point.setting && point.level !== "ok" ? (
              <Link to={`/admin/configuration?q=${encodeURIComponent(point.setting)}`}>
                {t("admin:system.security.change")}
              </Link>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function SystemVersion() {
  const t = useT();
  const format = useFormat();
  const version = useQuery({
    queryKey: VERSION_KEY,
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
            {v.update ? (
              <div>
                <dt>{t("admin:system.update.title")}</dt>
                <dd>
                  <UpdateStatus update={v.update} />
                </dd>
              </div>
            ) : null}
            {v.build?.commit || v.build?.date ? (
              <div>
                <dt>{t("admin:system.build")}</dt>
                <dd>
                  {v.build.commit ? <code title={v.build.commit}>{v.build.commit.slice(0, 8)}</code> : null}
                  {v.build.commit && v.build.date ? " · " : null}
                  {v.build.date ? format.dateTime(v.build.date) : null}
                </dd>
              </div>
            ) : null}
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
      {v?.security?.length ? (
        <AdminSection
          title={t("admin:system.security.title")}
          description={t("admin:system.security.hint")}
          icon="shield"
        >
          <SecurityPosture points={v.security} />
        </AdminSection>
      ) : null}
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
