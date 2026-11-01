import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { AdminSection, FormActions, FormGrid, StatusBadge } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, SelectField, TextAreaField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { EmptyState } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { templateName, useTemplates } from "./editions/api";

/**
 * Channels and automatic newsletters (027): the news desk's categories are channels — described, with an
 * icon, and e-mailed to their subscribers when « newsletter » is on (members unsubscribe per channel); a
 * schedule writes a channel's newsletter on its own (the week's releases, what arrived, what is coming).
 */
export type Channel = components["schemas"]["NewsCategoryOut"];
type Schedule = components["schemas"]["NewsletterScheduleOut"];
type ScheduleIn = components["schemas"]["NewsletterScheduleIn"];

const CHANNELS_KEY = ["admin", "news", "channels"] as const;
const SCHEDULES_KEY = ["admin", "news", "newsletters"] as const;
const ICONS = [
  "newspaper",
  "film",
  "tv",
  "book",
  "joystick",
  "music",
  "star",
  "sparkles",
  "megaphone",
  "calendar",
];

export function useChannels() {
  return useQuery({
    queryKey: CHANNELS_KEY,
    queryFn: async () => ((await api.GET("/api/v1/admin/news/categories")).data ?? []) as Channel[],
  });
}

function ChannelForm({ channel, onDone }: { channel?: Channel; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const [key, setKey] = useState(channel?.key ?? "");
  const [name, setName] = useState(channel?.name ?? "");
  const [description, setDescription] = useState(channel?.description ?? "");
  const [icon, setIcon] = useState(channel?.icon ?? "newspaper");
  const [newsletter, setNewsletter] = useState(channel?.newsletter ?? true);
  const [enabled, setEnabled] = useState(channel?.enabled ?? true);
  const save = useMutation({
    mutationFn: async () =>
      api.PUT("/api/v1/admin/news/categories", {
        body: { key, name, description, icon, newsletter, enabled, position: channel?.position ?? 0 },
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: CHANNELS_KEY });
      onDone();
    },
  });
  return (
    <form
      className="admin-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <FormGrid>
        <TextField
          label={t("news:channels.name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!channel)
              setKey(
                e.target.value
                  .normalize("NFKD")
                  .replace(/[^\w\s-]/g, "")
                  .trim()
                  .toLowerCase()
                  .replace(/[\s_]+/g, "-")
                  .slice(0, 60),
              );
          }}
        />
        <SelectField label={t("news:channels.icon")} value={icon} onChange={(e) => setIcon(e.target.value)}>
          {ICONS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("news:channels.description")}
          maxLength={300}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </FormGrid>
      <CheckboxField
        label={t("news:channels.newsletter")}
        hint={t("news:channels.newsletterHint")}
        checked={newsletter}
        onChange={(e) => setNewsletter(e.target.checked)}
      />
      <CheckboxField
        label={t("news:channels.enabled")}
        checked={enabled}
        onChange={(e) => setEnabled(e.target.checked)}
      />
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {save.error instanceof ApiError ? save.error.message : t("news:saveFailed")}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={save.isPending || !key}>
          <Icon name="check" size={16} />
          {t("news:save")}
        </Button>
      </FormActions>
    </form>
  );
}

export function ChannelsPanel() {
  const t = useT();
  const channels = useChannels();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <AdminSection
      title={t("news:channels.title")}
      description={t("news:channels.hint")}
      icon="megaphone"
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => setOpen(next ? "new" : null)}
          title={t("news:channels.new")}
          closeLabel={t("news:admin.close")}
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("news:channels.new")}
            </Button>
          }
        >
          <ChannelForm onDone={() => setOpen(null)} />
        </Dialog>
      }
    >
      {channels.data?.length === 0 ? (
        <EmptyState
          icon="megaphone"
          title={t("news:channels.empty")}
          action={{ label: t("news:channels.new"), onSelect: () => setOpen("new") }}
        />
      ) : null}
      <ul className="news-channels">
        {(channels.data ?? []).map((channel) => (
          <li key={channel.id} className="news-channel" data-disabled={!channel.enabled || undefined}>
            <span className="news-channel__icon" aria-hidden="true">
              <Icon name={channel.icon ?? "newspaper"} size={20} />
            </span>
            <span className="news-channel__text">
              <strong>{channel.name}</strong>
              <span className="admin-muted">{channel.description || channel.key}</span>
            </span>
            <span className="news-channel__badges">
              {channel.newsletter ? (
                <StatusBadge tone="ok">
                  <Icon name="mail" size={12} /> {t("news:channels.byEmail")}
                </StatusBadge>
              ) : (
                <StatusBadge tone="neutral">{t("news:channels.portalOnly")}</StatusBadge>
              )}
              {!channel.enabled ? <StatusBadge tone="warn">{t("news:channels.disabled")}</StatusBadge> : null}
            </span>
            <Dialog
              open={open === channel.id}
              onOpenChange={(next) => setOpen(next ? channel.id : null)}
              title={channel.name}
              closeLabel={t("news:admin.close")}
              trigger={
                <Button variant="ghost">
                  <Icon name="settings" size={16} />
                  {t("news:edit")}
                </Button>
              }
            >
              <ChannelForm channel={channel} onDone={() => setOpen(null)} />
            </Dialog>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
const MEDIA_KINDS = ["movie", "series", "book", "game", "album"] as const;

function ScheduleForm({ schedule, onDone }: { schedule?: Schedule; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const channels = useChannels();
  const templates = useTemplates();
  const [values, setValues] = useState<ScheduleIn>(
    schedule ?? {
      name: "",
      category_id: "",
      kind: "releases",
      media_kinds: [],
      cadence: "weekly",
      weekday: 4,
      hour: 18,
      language: (typeof document !== "undefined" && document.documentElement.lang.split("-")[0]) || "fr",
      email: true,
      enabled: true,
    },
  );
  const set = <K extends keyof ScheduleIn>(key: K, value: ScheduleIn[K]) =>
    setValues({ ...values, [key]: value });
  const save = useMutation({
    mutationFn: async () => {
      const body = { ...values, category_id: values.category_id || channels.data?.[0]?.id || "" };
      return schedule
        ? api.PUT("/api/v1/admin/news/newsletters/{schedule_id}", {
            params: { path: { schedule_id: schedule.id } },
            body,
          })
        : api.POST("/api/v1/admin/news/newsletters", { body });
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: SCHEDULES_KEY });
      onDone();
    },
  });
  const weekday = (day: number) =>
    new Date(2024, 0, 1 + day).toLocaleDateString(undefined, { weekday: "long" });
  return (
    <form
      className="admin-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <FormGrid>
        <TextField
          label={t("news:newsletters.name")}
          required
          maxLength={120}
          value={values.name}
          onChange={(e) => set("name", e.target.value)}
        />
        <SelectField
          label={t("news:newsletters.channel")}
          value={values.category_id || channels.data?.[0]?.id || ""}
          onChange={(e) => set("category_id", e.target.value)}
        >
          {(channels.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("news:newsletters.kind")}
          value={values.kind}
          onChange={(e) => set("kind", e.target.value as ScheduleIn["kind"])}
        >
          {(["edition", "releases", "additions", "upcoming"] as const).map((kind) => (
            <option key={kind} value={kind}>
              {t(`news:newsletters.kinds.${kind}`)}
            </option>
          ))}
        </SelectField>
        {values.kind === "edition" ? (
          // issue 316: an edition is drawn with a template
          <SelectField
            label={t("news:edition.admin.template")}
            value={values.template_key ?? "classic"}
            onChange={(e) => set("template_key", e.target.value)}
          >
            {(templates.data ?? []).map((tpl) => (
              <option key={tpl.key} value={tpl.key}>
                {templateName(t, tpl)}
              </option>
            ))}
          </SelectField>
        ) : null}
        <SelectField
          label={t("news:newsletters.cadence")}
          value={values.cadence}
          onChange={(e) => set("cadence", e.target.value as ScheduleIn["cadence"])}
        >
          {(["daily", "weekly", "monthly"] as const).map((cadence) => (
            <option key={cadence} value={cadence}>
              {t(`news:newsletters.cadences.${cadence}`)}
            </option>
          ))}
        </SelectField>
        {values.cadence !== "daily" ? (
          <SelectField
            label={t("news:newsletters.weekday")}
            value={String(values.weekday)}
            onChange={(e) => set("weekday", Number(e.target.value))}
          >
            {WEEKDAYS.map((day) => (
              <option key={day} value={day}>
                {weekday(day)}
              </option>
            ))}
          </SelectField>
        ) : null}
        <TextField
          label={t("news:newsletters.hour")}
          type="number"
          min={0}
          max={23}
          value={String(values.hour)}
          onChange={(e) => set("hour", Math.max(0, Math.min(23, Number(e.target.value))))}
        />
        <SelectField
          label={t("news:newsletters.language")}
          value={values.language}
          onChange={(e) => set("language", e.target.value)}
        >
          <option value="fr">Français</option>
          <option value="en">English</option>
        </SelectField>
      </FormGrid>
      {values.kind === "edition" ? (
        <TextAreaField
          label={t("news:edition.admin.notice")}
          hint={t("news:edition.admin.noticeHint")}
          rows={2}
          maxLength={2000}
          value={values.notice ?? ""}
          onChange={(e) => set("notice", e.target.value || null)}
        />
      ) : null}
      {values.kind === "edition" ? null : (
        <fieldset className="news-kinds">
          <legend>{t("news:newsletters.mediaKinds")}</legend>
          {MEDIA_KINDS.map((kind) => {
            const checked = (values.media_kinds ?? []).includes(kind);
            return (
              <label key={kind} className="service-picker__item" data-checked={checked || undefined}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    set(
                      "media_kinds",
                      checked
                        ? (values.media_kinds ?? []).filter((k) => k !== kind)
                        : [...(values.media_kinds ?? []), kind],
                    )
                  }
                />
                {t(`news:newsletters.mediaKind.${kind}`)}
              </label>
            );
          })}
          <span className="admin-muted">{t("news:newsletters.mediaKindsHint")}</span>
        </fieldset>
      )}
      <CheckboxField
        label={t("news:newsletters.email")}
        checked={values.email ?? true}
        onChange={(e) => set("email", e.target.checked)}
      />
      <CheckboxField
        label={t("news:newsletters.enabled")}
        checked={values.enabled ?? true}
        onChange={(e) => set("enabled", e.target.checked)}
      />
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {save.error instanceof ApiError ? save.error.message : t("news:saveFailed")}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={save.isPending || !channels.data?.length}>
          <Icon name="check" size={16} />
          {t("news:save")}
        </Button>
      </FormActions>
    </form>
  );
}

export function NewslettersPanel() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const channels = useChannels();
  const schedules = useQuery({
    queryKey: SCHEDULES_KEY,
    queryFn: async () => ((await api.GET("/api/v1/admin/news/newsletters")).data ?? []) as Schedule[],
  });
  const [open, setOpen] = useState<string | null>(null);
  const [ran, setRan] = useState<Record<string, string>>({});
  const run = useMutation({
    mutationFn: async (id: string) =>
      (
        (
          await api.POST("/api/v1/admin/news/newsletters/{schedule_id}/run", {
            params: { path: { schedule_id: id } },
          })
        ).data as { article: { title: string } | null }
      ).article,
    onSuccess: (article, id) => {
      setRan({
        ...ran,
        [id]: article
          ? t("news:newsletters.written", { title: article.title })
          : t("news:newsletters.nothing"),
      });
      void client.invalidateQueries({ queryKey: SCHEDULES_KEY });
      void client.invalidateQueries({ queryKey: ["news"] });
    },
  });
  const remove = useMutation({
    mutationFn: async (id: string) =>
      api.DELETE("/api/v1/admin/news/newsletters/{schedule_id}", { params: { path: { schedule_id: id } } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: SCHEDULES_KEY }),
  });
  const names = new Map((channels.data ?? []).map((c) => [c.id, c.name]));
  return (
    <AdminSection
      title={t("news:newsletters.title")}
      description={t("news:newsletters.hint")}
      icon="sparkles"
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => setOpen(next ? "new" : null)}
          title={t("news:newsletters.new")}
          closeLabel={t("news:admin.close")}
          size="lg"
          trigger={
            <Button disabled={!channels.data?.length}>
              <Icon name="plus" size={16} />
              {t("news:newsletters.new")}
            </Button>
          }
        >
          <ScheduleForm onDone={() => setOpen(null)} />
        </Dialog>
      }
    >
      {schedules.data?.length === 0 ? (
        <EmptyState
          icon="sparkles"
          title={t("news:newsletters.empty")}
          message={channels.data?.length ? undefined : t("news:newsletters.needChannel")}
          action={{ label: t("news:newsletters.new"), onSelect: () => setOpen("new") }}
        />
      ) : null}
      <ul className="news-channels">
        {(schedules.data ?? []).map((schedule) => (
          <li key={schedule.id} className="news-channel" data-disabled={!schedule.enabled || undefined}>
            <span className="news-channel__icon" aria-hidden="true">
              <Icon name={schedule.kind === "upcoming" ? "calendar" : "sparkles"} size={20} />
            </span>
            <span className="news-channel__text">
              <strong>{schedule.name}</strong>
              <span className="admin-muted">
                {names.get(schedule.category_id) ?? "—"} · {t(`news:newsletters.kinds.${schedule.kind}`)} ·{" "}
                {t(`news:newsletters.cadences.${schedule.cadence}`)}
                {schedule.next_run_at
                  ? ` · ${t("news:newsletters.next", { when: format.dateTime(schedule.next_run_at) })}`
                  : ""}
              </span>
              {ran[schedule.id] ? (
                <span role="status" className="services-admin__ok">
                  {ran[schedule.id]}
                </span>
              ) : null}
            </span>
            <span className="news-channel__badges">
              {schedule.email ? (
                <StatusBadge tone="ok">
                  <Icon name="mail" size={12} /> {t("news:channels.byEmail")}
                </StatusBadge>
              ) : null}
              {!schedule.enabled ? (
                <StatusBadge tone="warn">{t("news:channels.disabled")}</StatusBadge>
              ) : null}
            </span>
            <span className="news-channel__actions">
              <Button variant="secondary" disabled={run.isPending} onClick={() => run.mutate(schedule.id)}>
                <Icon name="play" size={14} />
                {t("news:newsletters.runNow")}
              </Button>
              <Dialog
                open={open === schedule.id}
                onOpenChange={(next) => setOpen(next ? schedule.id : null)}
                title={schedule.name}
                closeLabel={t("news:admin.close")}
                size="lg"
                trigger={
                  <Button variant="ghost">
                    <Icon name="settings" size={16} />
                    {t("news:edit")}
                  </Button>
                }
              >
                <ScheduleForm schedule={schedule} onDone={() => setOpen(null)} />
              </Dialog>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("news:newsletters.delete")}
                onClick={() => remove.mutate(schedule.id)}
              >
                <Icon name="trash" size={16} />
              </Button>
            </span>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}
