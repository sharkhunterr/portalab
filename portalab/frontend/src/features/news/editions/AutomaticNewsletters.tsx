import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { AdminSection, FormGrid, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextAreaField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { Switch } from "../../account/SettingsKit";
import { useChannels } from "../NewsChannels";
import {
  SCHEDULES,
  type Schedule,
  templateName,
  useContents,
  useEditionActions,
  usePreview,
  useSchedules,
  useTemplates,
} from "./api";
import { ContentPicker } from "./ContentPicker";
import { EditionFrame } from "./EditionsPage";
import { PreviewSwitch, useLivePreview } from "./PreviewSwitch";
import { TemplatePicker } from "./TemplatePicker";
import "./editions.css";

type ScheduleIn = components["schemas"]["NewsletterScheduleIn"];

const KEY = SCHEDULES;
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
    publish: true,
    enabled: true,
    notice: null,
    contents: null,
    charts: null,
    days: null,
  };
}

/** What the server takes back of a newsletter it gave (issue 328: its subscribers are not part of it). */
function input(schedule: Schedule): ScheduleIn {
  const {
    id: _id,
    last_run_at: _l,
    next_run_at: _n,
    last_article_id: _a,
    subscribers: _s,
    ...rest
  } = schedule;
  return { ...rest, kind: "edition" };
}

/** The edition a newsletter would write now, asked for a preview. */
function ask(values: ScheduleIn, defaults: ScheduleIn["contents"] | undefined) {
  return {
    template_key: values.template_key ?? "portalab",
    days: values.days ?? CADENCE_DAYS[values.cadence] ?? 7,
    language: values.language,
    notice: values.notice ?? null,
    category_id: values.category_id || null,
    contents: values.contents ?? defaults ?? null,
    charts: values.charts ?? null,
    subject: values.subject ?? null,
  };
}

/** A weekday's name in the interface's language (issue 328: not the browser's — no « Every vendredi »). */
function weekday(day: number, language: string): string {
  return new Date(2024, 0, 1 + day).toLocaleDateString(language, { weekday: "long" });
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
  const offered = useContents();
  const letters = (channels.data ?? []).filter((c) => c.newsletter && c.enabled);
  const [values, setValues] = useState<ScheduleIn>(() =>
    schedule ? input(schedule) : blank(letters[0]?.id ?? ""),
  );
  const set = <K extends keyof ScheduleIn>(key: K, value: ScheduleIn[K]) =>
    setValues({ ...values, [key]: value });
  const category = values.category_id || letters[0]?.id || "";
  const days = values.days ?? CADENCE_DAYS[values.cadence] ?? 7;
  const preview = usePreview();
  const { test } = useEditionActions();
  const [shown, setShown] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const subjectId = useId();
  const interfaceLanguage = useLocaleContext().language;
  const nowhere = !(values.publish ?? true) && !(values.email ?? true);
  const asked = () => ask({ ...values, category_id: category }, offered.data?.defaults);
  const [live, setLive] = useLivePreview();
  const write = (then?: (id: string) => void) =>
    preview.mutate(asked(), {
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
      const body = { ...values, kind: "edition" as const, category_id: category, contents: asked().contents };
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
                    {weekday(day, interfaceLanguage)}
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
            {t("news:auto.look")}
          </legend>
          {/* issue 329: its own template, chosen by sight */}
          <p className="admin-muted">{t("news:auto.lookHint")}</p>
          <TemplatePicker
            value={values.template_key ?? "portalab"}
            onChange={(key) => set("template_key", key)}
          />
        </fieldset>

        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">4</span>
            {t("news:auto.what")}
          </legend>
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
            <span className="email-setup__step">5</span>
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
          {/* issue 332: in the portal's news, by e-mail, or both */}
          <div className="auto-letter__switches">
            <Switch
              label={t("news:auto.publish")}
              checked={values.publish ?? true}
              onChange={(e) => set("publish", e.target.checked)}
            />
            <Switch
              label={t("news:auto.email")}
              checked={values.email ?? true}
              onChange={(e) => set("email", e.target.checked)}
            />
            {nowhere ? (
              <p role="alert" className="auto-letter__note" data-tone="warn">
                {t("news:auto.nowhere")}
              </p>
            ) : null}
            <Switch
              label={t("news:auto.enabled")}
              checked={values.enabled ?? true}
              onChange={(e) => set("enabled", e.target.checked)}
            />
          </div>
        </fieldset>

        {save.isError ? <p role="alert">{t("news:auto.saveFailed")}</p> : null}
        {test.isSuccess ? (
          <p role="status" className="services-admin__ok">
            {t(test.data ? "news:edition.admin.testSent" : "news:edition.admin.testFailed")}
          </p>
        ) : null}
        {/* issue 328: in its dialog, the actions sit in the footer, beside « Cancel » */}
        <DialogActions>
          <Button
            variant="secondary"
            disabled={test.isPending || preview.isPending}
            onClick={() => (live && shown ? test.mutate(shown) : write((id) => test.mutate(id)))}
          >
            <Icon name="mail" size={16} />
            {t("news:edition.admin.testMe")}
          </Button>
          <Button type="submit" disabled={save.isPending || !category || !values.name.trim() || nowhere}>
            <Icon name="check" size={16} />
            {t("news:auto.save")}
          </Button>
        </DialogActions>
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
 * issue 328: one automatic newsletter as a card — its name and its e-mail's subject, switched on or off in
 * place, what it is (when, where, with which template, to how many), and three actions: a test to me, its
 * settings (in a dialog), its deletion (confirmed).
 */
function NewsletterCard({
  schedule,
  channel,
  look,
  onEdit,
}: {
  schedule: Schedule;
  channel: string;
  look: string;
  onEdit: () => void;
}) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const interfaceLanguage = useLocaleContext().language;
  const toggle = useMutation({
    mutationFn: async (enabled: boolean) => {
      const { error } = await api.PUT("/api/v1/admin/news/newsletters/{schedule_id}", {
        params: { path: { schedule_id: schedule.id } },
        body: { ...input(schedule), enabled },
      });
      if (error) throw error;
    },
    onSettled: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const remove = useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE("/api/v1/admin/news/newsletters/{schedule_id}", {
        params: { path: { schedule_id: schedule.id } },
      });
      if (error) throw error;
    },
    onSuccess: () => {
      setConfirming(false);
      void client.invalidateQueries({ queryKey: KEY });
    },
  });
  // the letter it would write now, e-mailed to me alone — issue 334: and published in the news when it goes
  // there
  const test = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/admin/news/newsletters/{schedule_id}/test", {
        params: { path: { schedule_id: schedule.id } },
      });
      if (error) throw error;
      return data as { sent: boolean; article: string | null };
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: ["news"] }),
  });
  const enabled = toggle.isPending ? Boolean(toggle.variables) : schedule.enabled;
  const hour = String(schedule.hour).padStart(2, "0");
  const when =
    schedule.cadence === "daily"
      ? t("news:auto.everyDay", { hour })
      : t(`news:auto.every.${schedule.cadence}`, {
          day: weekday(schedule.weekday ?? 0, interfaceLanguage),
          hour,
        });
  return (
    <li className="auto-letter" data-off={!enabled || undefined}>
      <div className="auto-letter__head">
        <span className="auto-letter__icon" aria-hidden="true">
          <Icon name="sparkles" size={20} />
        </span>
        <span className="auto-letter__title">
          <strong>{schedule.name}</strong>
          {schedule.subject ? (
            <span className="auto-letter__subject">
              <Icon name="mail" size={14} />
              {schedule.subject}
            </span>
          ) : null}
        </span>
        <Switch
          label={t(enabled ? "news:auto.on" : "news:auto.off")}
          checked={enabled}
          disabled={toggle.isPending}
          onChange={(e) => toggle.mutate(e.target.checked)}
        />
      </div>
      <ul className="auto-letter__facts">
        <li>
          <Icon name="calendar" size={14} />
          {when}
        </li>
        <li>
          <Icon name="newspaper" size={14} />
          {channel}
        </li>
        <li>
          <Icon name="palette" size={14} />
          {look}
        </li>
        {/* issue 332: where it goes — the portal's news, e-mail (to how many — issue 326), or both */}
        {(schedule.publish ?? true) ? (
          <li>
            <Icon name="megaphone" size={14} />
            {t("news:auto.inNews")}
          </li>
        ) : null}
        {schedule.email ? (
          <li>
            <Icon name="mail" size={14} />
            {t("news:auto.subscribers", { count: schedule.subscribers ?? 0 })}
          </li>
        ) : null}
        {enabled && schedule.next_run_at ? (
          <li>
            <Icon name="clock" size={14} />
            {t("news:newsletters.next", { when: format.dateTime(schedule.next_run_at) })}
          </li>
        ) : null}
        {schedule.kind !== "edition" ? (
          <li>
            <StatusBadge tone="neutral">{t("news:auto.former")}</StatusBadge>
          </li>
        ) : null}
      </ul>
      <div className="auto-letter__actions">
        <Button variant="secondary" disabled={test.isPending} onClick={() => test.mutate()}>
          <Icon name={test.isPending ? "spinner" : "mail"} size={16} />
          {t("news:auto.test")}
        </Button>
        <Button variant="secondary" onClick={onEdit}>
          <Icon name="sliders" size={16} />
          {t("news:edit")}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("news:newsletters.delete")}
          onClick={() => setConfirming(true)}
        >
          <Icon name="trash" size={16} />
        </Button>
        {test.data ? (
          <span role="status" className="auto-letter__note" data-tone={test.data.sent ? "ok" : "warn"}>
            {t(test.data.sent ? "news:edition.admin.testSent" : "news:edition.admin.testFailed")}
            {test.data.article ? ` ${t("news:auto.testPublished")}` : ""}
          </span>
        ) : null}
        {test.isError || toggle.isError ? (
          <span role="alert" className="auto-letter__note" data-tone="warn">
            {t("news:auto.failed")}
          </span>
        ) : null}
      </div>
      <Dialog
        trigger={null}
        open={confirming}
        onOpenChange={setConfirming}
        title={t("news:auto.deleteTitle", { name: schedule.name })}
        description={t("news:auto.deleteHint")}
        closeLabel={t("news:edition.admin.cancel")}
        footer={
          <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
            <Icon name="trash" size={16} />
            {t("news:newsletters.delete")}
          </Button>
        }
      >
        {null}
      </Dialog>
    </li>
  );
}

/**
 * issue 325: the automatic newsletters — each a self-writing edition on its cadence; no drafts: what they
 * write is in the history below. Issue 328: as cards, set in a dialog.
 */
export function AutomaticNewsletters() {
  const t = useT();
  const channels = useChannels();
  const templates = useTemplates();
  const schedules = useSchedules();
  const [editing, setEditing] = useState<Schedule | "new" | null>(null);
  const names = new Map((channels.data ?? []).map((c) => [c.id, c.name]));
  const looks = new Map((templates.data ?? []).map((tpl) => [tpl.key, templateName(t, tpl)]));
  const hasChannel = (channels.data ?? []).some((c) => c.newsletter && c.enabled);
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
      <ul className="auto-letters">
        {(schedules.data ?? []).map((schedule) => (
          <NewsletterCard
            key={schedule.id}
            schedule={schedule}
            channel={names.get(schedule.category_id) ?? "—"}
            look={looks.get(schedule.template_key ?? "") ?? "—"}
            onEdit={() => setEditing(schedule)}
          />
        ))}
      </ul>
      <Dialog
        trigger={null}
        open={editing !== null}
        onOpenChange={(open) => (open ? null : setEditing(null))}
        title={editing === "new" || !editing ? t("news:newsletters.new") : editing.name}
        closeLabel={t("news:edition.admin.cancel")}
        size="full"
      >
        {editing ? (
          <NewsletterEditor
            key={editing === "new" ? "new" : editing.id}
            schedule={editing === "new" ? null : editing}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </Dialog>
    </AdminSection>
  );
}
