import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
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
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import "../admin.css";

interface Limit {
  limit: number | null;
  days: number | null;
}
interface Limits {
  movie: Limit;
  tv: Limit;
}
interface Window {
  limit: number | null;
  days: number | null;
  used: number;
  remaining: number | null;
  restricted: boolean;
}
interface Account {
  account: string;
  name: string | null;
  member: { id: string; name: string | null } | null;
  exempt: boolean;
  own: Limits;
  movie: Window | null;
  tv: Window | null;
}
interface Overview {
  service_id: string;
  defaults: Limits;
  accounts: Account[];
}

const KEY = ["admin", "media", "quotas"] as const;
const EMPTY: Limits = { movie: { limit: null, days: null }, tv: { limit: null, days: null } };

const number = (value: string): number | null => (value.trim() === "" ? null : Math.max(0, Number(value)));

/** Four fields — films and series, a number of requests every number of days (empty: the default). */
function LimitsFields({
  value,
  onChange,
  emptyHint,
}: {
  value: Limits;
  onChange: (next: Limits) => void;
  emptyHint: string;
}) {
  const t = useT();
  const field = (kind: "movie" | "tv", part: "limit" | "days") => (
    <TextField
      label={t(`media:quotaAdmin.${kind}.${part}`)}
      type="number"
      min={0}
      max={part === "limit" ? 1000 : 3650}
      inputMode="numeric"
      placeholder={emptyHint}
      value={value[kind][part] ?? ""}
      onChange={(event) =>
        onChange({ ...value, [kind]: { ...value[kind], [part]: number(event.target.value) } })
      }
    />
  );
  return (
    <FormGrid>
      {field("movie", "limit")}
      {field("movie", "days")}
      {field("tv", "limit")}
      {field("tv", "days")}
    </FormGrid>
  );
}

function Usage({ window, own, fallback }: { window: Window | null; own: Limit; fallback: Limit }) {
  const t = useT();
  const limit = own.limit ?? fallback.limit;
  const days = own.days ?? fallback.days;
  if (!limit) return <span>{t("media:quota.unlimited")}</span>;
  return (
    <span className="quota-admin__usage">
      <strong>{t("media:quotaAdmin.used", { used: window?.used ?? 0, limit })}</strong>
      <small>
        {days ? t("media:quota.every", { days }) : t("media:quota.always")}
        {own.limit === null ? ` · ${t("media:quotaAdmin.byDefault")}` : ""}
      </small>
      {window?.restricted ? <StatusBadge tone="warn">{t("media:quotaAdmin.reached")}</StatusBadge> : null}
    </span>
  );
}

function EditAccount({ account, onSave }: { account: Account; onSave: (limits: Limits) => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [limits, setLimits] = useState<Limits>(account.own);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setLimits(account.own);
      }}
      trigger={
        <Button
          variant="ghost"
          aria-label={`${t("media:quotaAdmin.edit")} ${account.name ?? account.account}`}
        >
          <Icon name="pencil" size={16} />
          {t("media:quotaAdmin.edit")}
        </Button>
      }
      title={t("media:quotaAdmin.editTitle", {
        name: account.member?.name ?? account.name ?? account.account,
      })}
      description={t("media:quotaAdmin.editHint")}
      closeLabel={t("media:discover.cancel")}
      footer={
        <Button
          onClick={() => {
            onSave(limits);
            setOpen(false);
          }}
        >
          <Icon name="check" size={16} />
          {t("media:quotaAdmin.save")}
        </Button>
      }
    >
      <LimitsFields value={limits} onChange={setLimits} emptyHint={t("media:quotaAdmin.default")} />
      <Button variant="secondary" onClick={() => setLimits(EMPTY)}>
        {t("media:quotaAdmin.useDefaults")}
      </Button>
    </Dialog>
  );
}

/**
 * #3: the request service's quotas, steered from the portal — its defaults (films and series: a number of
 * requests every number of days; empty or 0: no limit), then every account with the member it is, what it
 * used and its own limits, changed one by one or for a group at once. Every change is audited.
 */
function useOverview() {
  return useQuery({
    queryKey: KEY,
    retry: false,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/media/quotas");
      if (error) throw error;
      return data as unknown as Overview;
    },
  });
}

function useDone() {
  const client = useQueryClient();
  return (data: unknown) => {
    client.setQueryData(KEY, data as Overview);
    void client.invalidateQueries({ queryKey: ["media", "quota"] });
  };
}

/**
 * The request service's defaults (Seerr's own limits: films and series, a number of requests every number of
 * days) — also a step of the arrival wizard and of the setup assistant when Seerr is connected (issue 249).
 */
export function RequestQuotaDefaults() {
  const t = useT();
  const overview = useOverview();
  const done = useDone();
  const [defaults, setDefaults] = useState<Limits | null>(null);
  const [saved, setSaved] = useState(false);
  const saveDefaults = useMutation({
    mutationFn: async (limits: Limits) =>
      (await api.PUT("/api/v1/admin/media/quotas/defaults", { body: limits })).data,
    onSuccess: (data) => {
      done(data);
      setDefaults(null);
      setSaved(true);
    },
  });
  if (!overview.data) return null;
  const shown = defaults ?? overview.data.defaults ?? EMPTY;
  return (
    <AdminSection
      title={t("media:quotaAdmin.defaults")}
      description={t("media:quotaAdmin.defaultsHint")}
      icon="settings"
    >
      <LimitsFields
        value={shown}
        onChange={(next) => {
          setSaved(false);
          setDefaults(next);
        }}
        emptyHint={t("media:quota.unlimited")}
      />
      {saveDefaults.isError ? (
        <p role="alert" className="quota-admin__error">
          {t("media:quotaAdmin.failed")}
        </p>
      ) : null}
      <FormActions>
        {saved ? <p role="status">{t("media:quotaAdmin.saved")}</p> : null}
        <Button
          disabled={!defaults || saveDefaults.isPending}
          onClick={() => defaults && saveDefaults.mutate(defaults)}
        >
          <Icon name="check" size={16} />
          {t("media:quotaAdmin.save")}
        </Button>
      </FormActions>
    </AdminSection>
  );
}

export default function RequestQuotasAdmin() {
  const t = useT();
  const overview = useOverview();
  const [selected, setSelected] = useState<string[]>([]);
  const [bulk, setBulk] = useState<Limits>(EMPTY);
  const done = useDone();
  const saveOne = useMutation({
    mutationFn: async ({ account, limits }: { account: string; limits: Limits }) =>
      (
        await api.PUT("/api/v1/admin/media/quotas/accounts/{account}", {
          params: { path: { account } },
          body: limits,
        })
      ).data,
    onSuccess: done,
  });
  const saveMany = useMutation({
    mutationFn: async (limits: Limits) =>
      (await api.PUT("/api/v1/admin/media/quotas/accounts", { body: { ...limits, accounts: selected } }))
        .data,
    onSuccess: (data) => {
      done(data);
      setSelected([]);
    },
  });
  const data = overview.data;
  const failed = saveOne.isError || saveMany.isError;
  return (
    <AdminPage icon="coins" title={t("media:quotaAdmin.title")} description={t("media:quotaAdmin.pitch")}>
      {overview.isPending ? <FunctionalState state="loading" /> : null}
      {overview.isError ? (
        <AdminEmpty
          icon="inbox"
          title={t("media:quotaAdmin.none")}
          action={<Link to="/admin/services">{t("media:sources.addService")}</Link>}
        />
      ) : null}
      {failed ? (
        <p role="alert" className="quota-admin__error">
          {t("media:quotaAdmin.failed")}
        </p>
      ) : null}
      {data ? (
        <>
          <RequestQuotaDefaults />
          {selected.length ? (
            <AdminSection
              title={t("media:quotaAdmin.bulkTitle", { count: selected.length })}
              description={t("media:quotaAdmin.bulkHint")}
              icon="users"
            >
              <LimitsFields value={bulk} onChange={setBulk} emptyHint={t("media:quotaAdmin.default")} />
              <FormActions>
                <Button variant="secondary" onClick={() => setSelected([])}>
                  {t("media:discover.cancel")}
                </Button>
                <Button disabled={saveMany.isPending} onClick={() => saveMany.mutate(bulk)}>
                  <Icon name="check" size={16} />
                  {t("media:quotaAdmin.apply")}
                </Button>
              </FormActions>
            </AdminSection>
          ) : null}
          <AdminSection
            title={t("media:quotaAdmin.accounts")}
            description={t("media:quotaAdmin.accountsHint")}
            icon="users"
            flush
          >
            <AdminTable<Account>
              label={t("media:quotaAdmin.accounts")}
              rows={data.accounts}
              rowKey={(row) => row.account}
              columns={[
                {
                  key: "pick",
                  header: t("media:quotaAdmin.pick"),
                  width: "3rem",
                  render: (row) =>
                    row.exempt ? null : (
                      <input
                        type="checkbox"
                        aria-label={`${t("media:quotaAdmin.pick")} ${row.name ?? row.account}`}
                        checked={selected.includes(row.account)}
                        onChange={(event) =>
                          setSelected((current) =>
                            event.target.checked
                              ? [...current, row.account]
                              : current.filter((a) => a !== row.account),
                          )
                        }
                      />
                    ),
                },
                {
                  key: "who",
                  header: t("media:quotaAdmin.member"),
                  primary: true,
                  render: (row) => (
                    <span className="quota-admin__who">
                      <strong>{row.member?.name ?? row.name ?? row.account}</strong>
                      <small>
                        {row.member
                          ? row.name
                          : t("media:quotaAdmin.unlinked", { name: row.name ?? row.account })}
                      </small>
                    </span>
                  ),
                },
                {
                  key: "movie",
                  header: t("media:quota.kind.movie"),
                  render: (row) =>
                    row.exempt ? (
                      <StatusBadge tone="info">{t("media:quotaAdmin.exempt")}</StatusBadge>
                    ) : (
                      <Usage window={row.movie} own={row.own.movie} fallback={data.defaults.movie} />
                    ),
                },
                {
                  key: "tv",
                  header: t("media:quota.kind.tv"),
                  render: (row) =>
                    row.exempt ? null : (
                      <Usage window={row.tv} own={row.own.tv} fallback={data.defaults.tv} />
                    ),
                },
              ]}
              actions={(row) =>
                row.exempt ? null : (
                  <EditAccount
                    account={row}
                    onSave={(limits) => saveOne.mutate({ account: row.account, limits })}
                  />
                )
              }
            />
          </AdminSection>
        </>
      ) : null}
    </AdminPage>
  );
}
