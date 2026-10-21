import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useSearchParams } from "react-router";
import { api } from "../../../api/client";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminTable,
  AdminTabs,
  FormActions,
  FormGrid,
  StatusBadge,
  type Tone,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import "../admin.css";

/**
 * Maintenance windows (027; health 006 API; a page of the Operations hub — admin reorganisation, trial): schedule a maintenance of one service or of the whole
 * portal — members see it on the status page and in the banner while it runs — reschedule or cancel it,
 * and look back at past ones.
 */
interface Window {
  id: string;
  service_id: string | null;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  status: string;
  banner?: boolean;
}

interface ServiceItem {
  id: string;
  name: string;
}

const KEY = ["admin", "maintenance"] as const;
const TONE: Record<string, Tone> = { scheduled: "info", active: "warn", ended: "ok", cancelled: "neutral" };

function local(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function WindowForm({
  window: existing,
  services,
  service: preset,
}: {
  window?: Window | undefined;
  services: ServiceItem[];
  service?: string | undefined;
}) {
  const t = useT();
  const client = useQueryClient();
  const soon = new Date(Date.now() + 3600_000);
  const [service, setService] = useState(existing?.service_id ?? preset ?? "");
  const [title, setTitle] = useState(existing?.title ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [banner, setBanner] = useState(Boolean(existing?.banner));
  const [starts, setStarts] = useState(existing ? local(existing.starts_at) : local(soon.toISOString()));
  const [ends, setEnds] = useState(
    existing ? local(existing.ends_at) : local(new Date(soon.getTime() + 3600_000).toISOString()),
  );
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const save = useMutation({
    mutationFn: async () => {
      const times = { starts_at: new Date(starts).toISOString(), ends_at: new Date(ends).toISOString() };
      if (existing) {
        return api.PATCH("/api/v1/maintenance/{window_id}", {
          params: { path: { window_id: existing.id } },
          body: { title, description, ...times, reference_time_zone: zone, banner },
        });
      }
      return api.POST("/api/v1/maintenance", {
        body: {
          service_id: service || null,
          title,
          description,
          ...times,
          reference_time_zone: zone,
          banner,
        },
      });
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <form onSubmit={submit} className="admin-form admin-dialog-body">
      <FormGrid>
        <SelectField
          label={t("admin:maintenance.scope")}
          value={service}
          disabled={Boolean(existing)}
          onChange={(e) => setService(e.target.value)}
        >
          <option value="">{t("admin:maintenance.wholePortal")}</option>
          {services.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("admin:maintenance.title")}
          required
          maxLength={160}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <TextField
          label={t("admin:maintenance.starts")}
          type="datetime-local"
          required
          value={starts}
          onChange={(e) => setStarts(e.target.value)}
        />
        <TextField
          label={t("admin:maintenance.ends")}
          type="datetime-local"
          required
          value={ends}
          onChange={(e) => setEnds(e.target.value)}
        />
        <div className="ds-field" data-span="full">
          <label htmlFor="maintenance-description">{t("admin:maintenance.description")}</label>
          <textarea
            id="maintenance-description"
            rows={4}
            maxLength={4000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
      </FormGrid>
      <CheckboxField
        label={t("admin:maintenance.banner")}
        hint={t("admin:maintenance.bannerHint")}
        checked={banner}
        onChange={(e) => setBanner(e.target.checked)}
      />
      {save.isSuccess ? (
        <p role="status" className="services-admin__ok">
          {t("admin:maintenance.saved")}
        </p>
      ) : null}
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {save.error instanceof ApiError ? save.error.message : t("admin:maintenance.failed")}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={save.isPending}>
          <Icon name="check" size={16} />
          {existing ? t("admin:maintenance.reschedule") : t("admin:maintenance.schedule")}
        </Button>
      </FormActions>
    </form>
  );
}

/**
 * Maintenance windows, upcoming or past. ``?service=<id>`` (from a service's page) opens the form for that
 * service straight away.
 */
export function MaintenancePanel() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const preset = params.get("service") ?? undefined;
  const [creating, setCreating] = useState(Boolean(preset));
  const [view, setView] = useState("upcoming");
  const windows = useQuery({
    queryKey: [...KEY, view],
    queryFn: async () =>
      (
        (await api.GET("/api/v1/maintenance", { params: { query: { include_past: view === "past" } } }))
          .data as unknown as {
          items: Window[];
        }
      ).items,
  });
  const services = useQuery({
    queryKey: ["admin", "services"],
    queryFn: async () =>
      ((await api.GET("/api/v1/services")).data as unknown as { items: ServiceItem[] }).items,
  });
  const cancel = useMutation({
    mutationFn: async (id: string) =>
      api.DELETE("/api/v1/maintenance/{window_id}", { params: { path: { window_id: id } } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const names = new Map((services.data ?? []).map((s) => [s.id, s.name]));
  const rows = (windows.data ?? []).filter(
    (w) => view === "upcoming" || ["ended", "cancelled"].includes(w.status),
  );
  return (
    <>
      <AdminSection
        title={t("admin:maintenance.windows")}
        icon="wrench"
        flush
        actions={
          <>
            <AdminTabs
              label={t("admin:maintenance.pageTitle")}
              current={view}
              onChange={setView}
              tabs={[
                { key: "upcoming", label: t("admin:maintenance.upcoming") },
                { key: "past", label: t("admin:maintenance.past") },
              ]}
            />
            <Dialog
              size="lg"
              title={t("admin:maintenance.new")}
              closeLabel={t("admin:services.close")}
              open={creating}
              onOpenChange={(next) => {
                setCreating(next);
                if (!next && preset) setParams({}, { replace: true });
              }}
              trigger={
                <Button>
                  <Icon name="plus" size={16} />
                  {t("admin:maintenance.new")}
                </Button>
              }
            >
              <WindowForm services={services.data ?? []} service={preset} />
            </Dialog>
          </>
        }
      >
        <AdminTable<Window>
          label={t("admin:maintenance.pageTitle")}
          rows={rows}
          rowKey={(w) => w.id}
          empty={
            <AdminEmpty
              icon="wrench"
              title={t("admin:maintenance.none")}
              action={<span className="admin-muted">{t("admin:maintenance.noneHint")}</span>}
            />
          }
          columns={[
            {
              key: "title",
              header: t("admin:maintenance.title"),
              primary: true,
              render: (w) => (
                <span className="services-admin__name">
                  <strong>{w.title}</strong>
                  <span className="admin-muted">
                    {w.service_id
                      ? (names.get(w.service_id) ?? w.service_id)
                      : t("admin:maintenance.wholePortal")}
                  </span>
                </span>
              ),
            },
            {
              key: "when",
              header: t("admin:maintenance.when"),
              render: (w) => `${format.dateTime(w.starts_at)} → ${format.dateTime(w.ends_at)}`,
            },
            {
              key: "status",
              header: t("admin:maintenance.status"),
              render: (w) => (
                <StatusBadge tone={TONE[w.status] ?? "neutral"}>
                  {t(`admin:maintenance.states.${w.status}`)}
                </StatusBadge>
              ),
            },
          ]}
          actions={(w) =>
            w.status === "scheduled" || w.status === "active" ? (
              <>
                <Dialog
                  size="lg"
                  title={w.title}
                  closeLabel={t("admin:services.close")}
                  trigger={<Button variant="secondary">{t("admin:maintenance.edit")}</Button>}
                >
                  <WindowForm window={w} services={services.data ?? []} />
                </Dialog>
                <Button variant="ghost" onClick={() => cancel.mutate(w.id)}>
                  {t("admin:maintenance.cancel")}
                </Button>
              </>
            ) : null
          }
        />
      </AdminSection>
    </>
  );
}

/** ``/admin/maintenance`` — the maintenances, a page of the Operations hub. */
export default function MaintenanceAdmin() {
  const t = useT();
  return (
    <AdminPage
      icon="wrench"
      title={t("admin:maintenance.pageTitle")}
      description={t("admin:maintenance.subtitle")}
    >
      <MaintenancePanel />
    </AdminPage>
  );
}
