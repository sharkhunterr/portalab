import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { AdminSection, FormActions, FormGrid, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import {
  CheckboxField,
  SelectField,
  TextAreaField,
  TextField,
} from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useChannels } from "../NewsChannels";
import { templateName, useContents, useEditionActions, usePreview, useTemplates } from "./api";
import { ContentPicker } from "./ContentPicker";
import { EditionFrame } from "./EditionsPage";
import { PreviewSwitch, useLivePreview } from "./PreviewSwitch";
import "./editions.css";

type Schedule = components["schemas"]["NewsletterScheduleOut"];
type ScheduleIn = components["schemas"]["NewsletterScheduleIn"];

const KEY = ["admin", "news", "newsletters"] as const;
const CADENCE_DAYS: Record<string, number> = { daily: 1, weekly: 7, monthly: 30 };
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
// the e-mail subject's variables, offered as chips (the server also reads their English names)
const VARIABLES = ["site", "date", "semaine", "mois", "année", "période", "numéro", "chaîne"];

function language(): string {
  return (typeof document !== "undefined" && document.documentElement.lang.split("-")[0]) || "fr";
}

function blank(category: string): ScheduleIn {
  return {
    name: "",
    subject: "{site} — la lettre de la semaine {semaine}",
    category_id: category,
    kind: "edition",
    template_key: "portalab",
    media_kinds: [],
    cadence: "weekly",
    weekday: 4,
    hour: 18,
    language: language(),
    email: true,
    enabled: true,
    notice: null,
    contents: null,
    charts: null,
    days: null,
  };
}

/**
 * issue 325: one automatic newsletter, set in the order it is thought — its name (for the news desk) and its
 * e-mail's subject (with variables), when it goes out and over how many days, its template, what it tells
 * (contents, charts), its notice, where it goes — previewed live with the real data, sent as a test to me.
 */
function NewsletterEditor({ schedule, onDone }: { schedule: Schedule | null; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const channels = useChannels();
  const templates = useTemplates();
  const offered = useContents();
  const letters = (channels.data ?? []).filter((c) => c.newsletter && c.enabled);
  const [values, setValues] = useState<ScheduleIn>(() => {
    if (!schedule) return blank(letters[0]?.id ?? "");
    const { id: _id, last_run_at: _l, next_run_at: _n, last_article_id: _a, ...rest } = schedule;
    return { ...rest, kind: "edition" };
  });
  const set = <K extends keyof ScheduleIn>(key: K, value: ScheduleIn[K]) =>
    setValues({ ...values, [key]: value });
  const category = values.category_id || letters[0]?.id || "";
  const days = values.days ?? CADENCE_DAYS[values.cadence] ?? 7;
  const preview = usePreview();
  const { test } = useEditionActions();
  const [shown, setShown] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const subjectId = useId();
  const ask = () => ({
    template_key: values.template_key ?? "portalab",
    days,
    language: values.language,
    notice: values.notice ?? null,
    category_id: category || null,
    contents: values.contents ?? offered.data?.defaults ?? null,
    charts: values.charts ?? null,
    subject: values.subject ?? null,
  });
  const [live, setLive] = useLivePreview();
  const write = (then?: (id: string) => void) =>
    preview.mutate(ask(), {
      onSuccess: (edition) => {
        setShown(edition.id);
        then?.(edition.id);
      },
    });
  // biome-ignore lint/correctness/useExhaustiveDependencies: issue 327 — live, a preview a moment after each change
  useEffect(() => {
    if (!live) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => write(), 800);
    return () => window.clearTimeout(timer.current);
  }, [values, offered.data, live]);
  const save = useMutation({
    mutationFn: async () => {
      const body = { ...values, kind: "edition" as const, category_id: category, contents: ask().contents };
      const { error } = schedule
        ? await api.PUT("/api/v1/admin/news/newsletters/{schedule_id}", {
            params: { path: { schedule_id: schedule.id } },
            body,
          })
        : await api.POST("/api/v1/admin/news/newsletters", { body });
      if (error) throw error;
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      onDone();
    },
  });
  const insert = (variable: string) => {
    const field = document.getElementById(subjectId) as HTMLInputElement | null;
    const text = values.subject ?? "";
    const at = field?.selectionStart ?? text.length;
    set("subject", `${text.slice(0, at)}{${variable}}${text.slice(at)}`);
  };
  const weekday = (day: number) =>
    new Date(2024, 0, 1 + day).toLocaleDateString(undefined, { weekday: "long" });
  return (
    <div className="edition-editor">
      <form
        className="admin-form edition-editor__form"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">1</span>
            {t("news:auto.identity")}
          </legend>
          <TextField
            label={t("news:auto.name")}
            hint={t("news:auto.nameHint")}
            required
            maxLength={120}
            value={values.name}
            onChange={(e) => set("name", e.target.value)}
          />
          <TextField
            id={subjectId}
            label={t("news:auto.subject")}
            hint={t("news:auto.subjectHint")}
            maxLength={200}
            value={values.subject ?? ""}
            onChange={(e) => set("subject", e.target.value || null)}
          />
          <div className="edition-variables" role="group" aria-label={t("news:auto.variables")}>
            {VARIABLES.map((variable) => (
              <button
                key={variable}
                type="button"
                className="edition-variable"
                onClick={() => insert(variable)}
              >
                {`{${variable}}`}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">2</span>
            {t("news:auto.when")}
          </legend>
          <FormGrid>
            <SelectField
              label={t("news:newsletters.cadence")}
              value={values.cadence}
              onChange={(e) =>
                setValues({ ...values, cadence: e.target.value as ScheduleIn["cadence"], days: null })
              }
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
              label={t("news:edition.admin.period")}
              value={String(days)}
              onChange={(e) => set("days", Number(e.target.value))}
            >
              {[1, 7, 14, 30, 90].map((n) => (
                <option key={n} value={n}>
                  {t("news:edition.admin.days", { count: n })}
                </option>
              ))}
            </SelectField>
          </FormGrid>
        </fieldset>

        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">3</span>
            {t("news:auto.what")}
          </legend>
          <SelectField
            label={t("news:edition.admin.template")}
            value={values.template_key ?? "portalab"}
            onChange={(e) => set("template_key", e.target.value)}
          >
            {(templates.data ?? []).map((tpl) => (
              <option key={tpl.key} value={tpl.key}>
                {templateName(t, tpl)}
              </option>
            ))}
          </SelectField>
          <ContentPicker
            value={values.contents ?? null}
            onChange={(contents) => set("contents", contents)}
            charts={values.charts ?? null}
            onCharts={(charts) => set("charts", charts)}
          />
          <TextAreaField
            label={t("news:edition.admin.notice")}
            hint={t("news:edition.admin.noticeHint")}
            rows={2}
            maxLength={2000}
            value={values.notice ?? ""}
            onChange={(e) => set("notice", e.target.value || null)}
          />
        </fieldset>

        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">4</span>
            {t("news:auto.where")}
          </legend>
          <FormGrid>
            <SelectField
              label={t("news:newsletters.channel")}
              value={category}
              onChange={(e) => set("category_id", e.target.value)}
            >
              {letters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </SelectField>
            <SelectField
              label={t("news:newsletters.language")}
              value={values.language}
              onChange={(e) => set("language", e.target.value)}
            >
              <option value="fr">Français</option>
              <option value="en">English</option>
            </SelectField>
          </FormGrid>
          <CheckboxField
            label={t("news:auto.email")}
            checked={values.email ?? true}
            onChange={(e) => set("email", e.target.checked)}
          />
          <CheckboxField
            label={t("news:auto.enabled")}
            checked={values.enabled ?? true}
            onChange={(e) => set("enabled", e.target.checked)}
          />
        </fieldset>

        {save.isError ? <p role="alert">{t("news:auto.saveFailed")}</p> : null}
        {test.isSuccess ? (
          <p role="status" className="services-admin__ok">
            {t(test.data ? "news:edition.admin.testSent" : "news:edition.admin.testFailed")}
          </p>
        ) : null}
        <FormActions>
          <Button variant="ghost" onClick={onDone}>
            {t("news:edition.admin.cancel")}
          </Button>
          <Button
            variant="secondary"
            disabled={test.isPending || preview.isPending}
            onClick={() => (live && shown ? test.mutate(shown) : write((id) => test.mutate(id)))}
          >
            <Icon name="mail" size={16} />
            {t("news:edition.admin.testMe")}
          </Button>
          <Button type="submit" disabled={save.isPending || !category || !values.name.trim()}>
            <Icon name="check" size={16} />
            {t("news:auto.save")}
          </Button>
        </FormActions>
      </form>
      <div className="edition-editor__preview" aria-busy={preview.isPending || undefined}>
        <PreviewSwitch live={live} onLive={setLive} onPreview={() => write()} busy={preview.isPending} />
        {shown ? (
          <EditionFrame src={`/api/v1/admin/news/newsletter-editions/${shown}/page`} title={values.name} />
        ) : (
          <p className="admin-muted">{t("news:edition.admin.noPreview")}</p>
        )}
      </div>
    </div>
  );
}

/**
 * issue 325: the automatic newsletters — each a self-writing edition on its cadence (its name, its e-mail's
 * subject, its next run), run now or set; no drafts: what they write is in the history below.
 */
export function AutomaticNewsletters() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const channels = useChannels();
  const templates = useTemplates();
  const schedules = useQuery({
    queryKey: KEY,
    queryFn: async () => ((await api.GET("/api/v1/admin/news/newsletters")).data ?? []) as Schedule[],
  });
  const [editing, setEditing] = useState<Schedule | "new" | null>(null);
  const [ran, setRan] = useState<Record<string, string>>({});
  const run = useMutation({
    mutationFn: async (id: string) =>
      (
        await api.POST("/api/v1/admin/news/newsletters/{schedule_id}/run", {
          params: { path: { schedule_id: id } },
        })
      ).data as { edition: string | null; article: unknown },
    onSuccess: (done, id) => {
      setRan({ ...ran, [id]: done.edition ? t("news:auto.ran") : t("news:newsletters.nothing") });
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["news", "editions"] });
    },
  });
  const remove = useMutation({
    mutationFn: async (id: string) =>
      api.DELETE("/api/v1/admin/news/newsletters/{schedule_id}", { params: { path: { schedule_id: id } } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const names = new Map((channels.data ?? []).map((c) => [c.id, c.name]));
  const looks = new Map((templates.data ?? []).map((tpl) => [tpl.key, templateName(t, tpl)]));
  const hasChannel = (channels.data ?? []).some((c) => c.newsletter && c.enabled);
  if (editing)
    return (
      <AdminSection
        icon="sparkles"
        title={editing === "new" ? t("news:newsletters.new") : editing.name}
        span="full"
      >
        <NewsletterEditor schedule={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      </AdminSection>
    );
  return (
    <AdminSection
      icon="sparkles"
      title={t("news:newsletters.title")}
      description={t("news:auto.intro")}
      span="full"
      actions={
        <Button disabled={!hasChannel} onClick={() => setEditing("new")}>
          <Icon name="plus" size={16} />
          {t("news:newsletters.new")}
        </Button>
      }
    >
      {schedules.data?.length === 0 ? (
        <EmptyState
          icon="sparkles"
          title={t("news:newsletters.empty")}
          message={hasChannel ? t("news:auto.emptyHint") : t("news:newsletters.needChannel")}
          action={{ label: t("news:newsletters.new"), onSelect: () => setEditing("new") }}
        />
      ) : null}
      <ul className="news-channels">
        {(schedules.data ?? []).map((schedule) => (
          <li key={schedule.id} className="news-channel" data-disabled={!schedule.enabled || undefined}>
            <span className="news-channel__icon" aria-hidden="true">
              <Icon name="sparkles" size={20} />
            </span>
            <span className="news-channel__text">
              <strong>{schedule.name}</strong>
              {schedule.subject ? <span className="edition-subject">✉ {schedule.subject}</span> : null}
              <span className="admin-muted">
                {names.get(schedule.category_id) ?? "—"} · {looks.get(schedule.template_key ?? "") ?? "—"} ·{" "}
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
                  <Icon name="mail" size={12} />{" "}
                  {schedule.subscribers != null
                    ? t("news:auto.subscribers", { count: schedule.subscribers }) // issue 326
                    : t("news:channels.byEmail")}
                </StatusBadge>
              ) : null}
              {!schedule.enabled ? (
                <StatusBadge tone="warn">{t("news:channels.disabled")}</StatusBadge>
              ) : null}
              {schedule.kind !== "edition" ? (
                <StatusBadge tone="neutral">{t("news:auto.former")}</StatusBadge>
              ) : null}
            </span>
            <span className="news-channel__actions">
              <Button variant="secondary" disabled={run.isPending} onClick={() => run.mutate(schedule.id)}>
                <Icon name="send" size={14} />
                {t("news:auto.runNow")}
              </Button>
              <Button variant="ghost" onClick={() => setEditing(schedule)}>
                <Icon name="settings" size={16} />
                {t("news:edit")}
              </Button>
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
