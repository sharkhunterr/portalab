import { useEffect, useRef, useState } from "react";
import { AdminSection, FormGrid, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import {
  type Definition,
  type Section,
  templateAbout,
  templateName,
  useAdminEditions,
  useDeleteTemplate,
  useEditionActions,
  usePreview,
  useSaveTemplate,
  useSchedules,
  useTemplates,
} from "./api";
import { EditionFrame } from "./EditionsPage";
import { PreviewSwitch, useLivePreview } from "./PreviewSwitch";
import { Swatches } from "./TemplatePicker";
import "./editions.css";

const KINDS: Section["kind"][] = [
  "notice",
  "stats",
  "top",
  "additions",
  "requests",
  "releases",
  "tv",
  "upcoming",
  "articles",
];
const LAYOUTS: NonNullable<Section["layout"]>[] = ["grid", "list", "hero", "compact"];
const MEDIA: NonNullable<Section["media"]>[number][] = [
  "movie",
  "series",
  "book",
  "audiobook",
  "game",
  "album",
];
const COLORS: Array<keyof Definition["palette"]> = [
  "background",
  "surface",
  "text",
  "muted",
  "accent",
  "accent_text",
  "border",
];
const TITLED = new Set(["top", "additions", "requests", "releases", "tv", "upcoming", "articles"]);

function language(): string {
  return (typeof document !== "undefined" && document.documentElement.lang.split("-")[0]) || "fr";
}

/** A page of an edition — a preview or a draft — framed for the news desk. */
function Preview({ id, title }: { id: string | null; title: string }) {
  const t = useT();
  if (!id) return <p className="admin-muted">{t("news:edition.admin.noPreview")}</p>;
  return <EditionFrame src={`/api/v1/admin/news/newsletter-editions/${id}/page`} title={title} />;
}

/** One section of a template: what it tells, how, how many titles, of which kinds. */
function SectionRow({
  section,
  index,
  count,
  onChange,
  onMove,
  onRemove,
}: {
  section: Section;
  index: number;
  count: number;
  onChange: (next: Section) => void;
  onMove: (by: -1 | 1) => void;
  onRemove: () => void;
}) {
  const t = useT();
  const titled = TITLED.has(section.kind);
  return (
    <li className="edition-section">
      <div className="edition-section__head">
        <span className="edition-section__rank">{index + 1}</span>
        <SelectField
          label={t("news:edition.admin.sectionKind")}
          value={section.kind}
          onChange={(e) => onChange({ ...section, kind: e.target.value as Section["kind"] })}
        >
          {KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {t(`news:edition.section.${kind}`)}
            </option>
          ))}
        </SelectField>
        <div className="edition-section__moves">
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("news:edition.admin.up")}
            disabled={index === 0}
            onClick={() => onMove(-1)}
          >
            <Icon name="arrow-up" size={16} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("news:edition.admin.down")}
            disabled={index === count - 1}
            onClick={() => onMove(1)}
          >
            <Icon name="arrow-down" size={16} />
          </Button>
          <Button variant="ghost" size="icon" aria-label={t("news:edition.admin.remove")} onClick={onRemove}>
            <Icon name="trash" size={16} />
          </Button>
        </div>
      </div>
      {titled ? (
        <div className="edition-section__body">
          <SelectField
            label={t("news:edition.admin.layout")}
            value={section.layout ?? "grid"}
            onChange={(e) => onChange({ ...section, layout: e.target.value as Section["layout"] })}
          >
            {LAYOUTS.map((layout) => (
              <option key={layout} value={layout}>
                {t(`news:edition.layout.${layout}`)}
              </option>
            ))}
          </SelectField>
          {section.layout === "grid" || section.layout === "hero" || !section.layout ? (
            <SelectField
              label={t("news:edition.admin.columns")}
              value={String(section.columns ?? 3)}
              onChange={(e) => onChange({ ...section, columns: Number(e.target.value) })}
            >
              {[2, 3, 4].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </SelectField>
          ) : null}
          <TextField
            label={t("news:edition.admin.limit")}
            type="number"
            min={1}
            max={24}
            value={String(section.limit ?? 8)}
            onChange={(e) =>
              onChange({ ...section, limit: Math.max(1, Math.min(24, Number(e.target.value) || 1)) })
            }
          />
          <TextField
            label={t("news:edition.admin.sectionTitle")}
            maxLength={80}
            placeholder={t(`news:edition.section.${section.kind}`)}
            value={section.title ?? ""}
            onChange={(e) => onChange({ ...section, title: e.target.value || null })}
          />
          {section.kind !== "articles" ? (
            <fieldset className="news-kinds edition-section__media">
              <legend>{t("news:edition.admin.media")}</legend>
              {MEDIA.map((kind) => {
                const checked = (section.media ?? []).includes(kind);
                return (
                  <label key={kind} className="service-picker__item" data-checked={checked || undefined}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() =>
                        onChange({
                          ...section,
                          media: checked
                            ? (section.media ?? []).filter((m) => m !== kind)
                            : [...(section.media ?? []), kind],
                        })
                      }
                    />
                    {t(`news:edition.group.${kind}`)}
                  </label>
                );
              })}
            </fieldset>
          ) : null}
          <CheckboxField
            label={t("news:edition.admin.overview")}
            checked={section.overview ?? true}
            onChange={(e) => onChange({ ...section, overview: e.target.checked })}
          />
        </div>
      ) : null}
    </li>
  );
}

/**
 * A template being written: its look (name over the title, header, font, corners, palette) and its sections in
 * their order — previewed as it goes with the portal's real data, as the e-mail would be.
 */
function TemplateEditor({
  start,
  startKey,
  onDone,
}: {
  start: Definition;
  startKey: string | null;
  onDone: () => void;
}) {
  const t = useT();
  const [definition, setDefinition] = useState<Definition>(start);
  const [key, setKey] = useState(startKey ?? "");
  const save = useSaveTemplate();
  const preview = usePreview();
  const [shown, setShown] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const set = <K extends keyof Definition>(field: K, value: Definition[K]) =>
    setDefinition({ ...definition, [field]: value });
  const sections = definition.sections;
  const setSections = (next: Section[]) => set("sections", next);
  const [live, setLive] = useLivePreview();
  const write = () =>
    preview.mutate(
      { template_key: key || "draft", days: 7, language: language(), definition, notice: null },
      { onSuccess: (edition) => setShown(edition.id) },
    );
  // biome-ignore lint/correctness/useExhaustiveDependencies: issue 327 — live, a preview a moment after each change
  useEffect(() => {
    if (!live) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(write, 700);
    return () => window.clearTimeout(timer.current);
  }, [definition, live]);
  const valid = /^[a-z0-9][a-z0-9_-]{1,62}$/.test(key) && definition.name.trim().length > 0;
  return (
    <div className="edition-editor">
      <form
        className="admin-form edition-editor__form"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) save.mutate({ key, definition }, { onSuccess: onDone });
        }}
      >
        <FormGrid>
          <TextField
            label={t("news:edition.admin.name")}
            required
            maxLength={80}
            value={definition.name}
            onChange={(e) => set("name", e.target.value)}
          />
          <TextField
            label={t("news:edition.admin.key")}
            hint={t("news:edition.admin.keyHint")}
            required
            disabled={Boolean(startKey)}
            pattern="[a-z0-9][a-z0-9_\-]{1,62}"
            value={key}
            onChange={(e) => setKey(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "-"))}
          />
          <TextField
            label={t("news:edition.admin.brand")}
            hint={t("news:edition.admin.brandHint")}
            maxLength={60}
            value={definition.brand ?? ""}
            onChange={(e) => set("brand", e.target.value)}
          />
          <TextField
            label={t("news:edition.admin.tagline")}
            maxLength={160}
            value={definition.tagline ?? ""}
            onChange={(e) => set("tagline", e.target.value)}
          />
          <SelectField
            label={t("news:edition.admin.header")}
            value={definition.header ?? "banner"}
            onChange={(e) => set("header", e.target.value as Definition["header"])}
          >
            {(["brand", "banner", "centered", "minimal"] as const).map((header) => (
              <option key={header} value={header}>
                {t(`news:edition.header.${header}`)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label={t("news:edition.admin.font")}
            value={definition.font ?? "sans"}
            onChange={(e) => set("font", e.target.value as Definition["font"])}
          >
            {(["brand", "sans", "serif", "rounded", "mono"] as const).map((font) => (
              <option key={font} value={font}>
                {t(`news:edition.font.${font}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("news:edition.admin.radius")}
            type="number"
            min={0}
            max={24}
            value={String(definition.radius ?? 12)}
            onChange={(e) => set("radius", Math.max(0, Math.min(24, Number(e.target.value) || 0)))}
          />
        </FormGrid>
        <fieldset className="edition-palette">
          <legend>{t("news:edition.admin.palette")}</legend>
          {COLORS.map((color) => (
            <label key={color} className="edition-palette__color">
              <input
                type="color"
                value={definition.palette[color]}
                onChange={(e) => set("palette", { ...definition.palette, [color]: e.target.value })}
              />
              <span>{t(`news:edition.color.${color}`)}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="edition-sections">
          <legend>{t("news:edition.admin.sections")}</legend>
          <ol>
            {sections.map((section, index) => (
              <SectionRow
                // biome-ignore lint/suspicious/noArrayIndexKey: sections have no identity of their own
                key={index}
                section={section}
                index={index}
                count={sections.length}
                onChange={(next) => setSections(sections.map((s, i) => (i === index ? next : s)))}
                onMove={(by) => {
                  const next = [...sections];
                  const [moved] = next.splice(index, 1);
                  if (moved) next.splice(index + by, 0, moved);
                  setSections(next);
                }}
                onRemove={() => setSections(sections.filter((_, i) => i !== index))}
              />
            ))}
          </ol>
          <Button
            variant="secondary"
            disabled={sections.length >= 12}
            onClick={() =>
              setSections([
                ...sections,
                { kind: "additions", layout: "grid", limit: 8, columns: 3, overview: true },
              ])
            }
          >
            <Icon name="plus" size={16} />
            {t("news:edition.admin.addSection")}
          </Button>
        </fieldset>
        {save.isError ? <p role="alert">{t("news:edition.admin.saveFailed")}</p> : null}
        {/* issue 329: in its dialog, beside « Cancel » */}
        <DialogActions>
          <Button type="submit" disabled={!valid || !sections.length || save.isPending}>
            <Icon name="check" size={16} />
            {t("news:edition.admin.save")}
          </Button>
        </DialogActions>
      </form>
      <div className="edition-editor__preview" aria-busy={preview.isPending || undefined}>
        <PreviewSwitch live={live} onLive={setLive} onPreview={write} busy={preview.isPending} />
        <Preview id={shown} title={definition.name} />
      </div>
    </div>
  );
}

/**
 * issue 316: the templates — the built-in ones to copy, the news desk's own to change. Issue 329: each
 * automatic newsletter has its own; every template says which ones use it, and is set in a dialog.
 */
function Templates() {
  const t = useT();
  const templates = useTemplates();
  const schedules = useSchedules();
  const remove = useDeleteTemplate();
  const [editing, setEditing] = useState<{ definition: Definition; key: string | null } | null>(null);
  const users = (key: string) =>
    (schedules.data ?? []).filter((s) => (s.template_key ?? "portalab") === key).map((s) => s.name);
  return (
    <AdminSection
      icon="palette"
      title={t("news:edition.admin.templates")}
      description={t("news:edition.admin.templatesHint")}
      span="full"
    >
      <ul className="edition-templates">
        {(templates.data ?? []).map((template) => (
          <li key={template.key}>
            <Swatches template={template} />
            <span className="edition-templates__text">
              <strong>{templateName(t, template)}</strong>
              <small>{templateAbout(t, template)}</small>
              <span className="edition-templates__badges">
                {template.builtin ? (
                  <StatusBadge tone="neutral">{t("news:edition.admin.builtin")}</StatusBadge>
                ) : null}
                <span className="edition-templates__users">
                  <Icon name="sparkles" size={12} />
                  {users(template.key).length
                    ? t("news:auto.usedBy", { names: users(template.key).join(", ") })
                    : t("news:auto.usedByNone")}
                </span>
              </span>
            </span>
            <span className="edition-templates__actions">
              <Button
                variant="ghost"
                onClick={() =>
                  setEditing({
                    definition: {
                      ...template.definition,
                      name: `${templateName(t, template)} (${t("news:edition.admin.copy")})`,
                    },
                    key: null,
                  })
                }
              >
                <Icon name="copy" size={16} />
                {t("news:edition.admin.duplicate")}
              </Button>
              {template.builtin ? null : (
                <>
                  <Button
                    variant="ghost"
                    onClick={() => setEditing({ definition: template.definition, key: template.key })}
                  >
                    <Icon name="settings" size={16} />
                    {t("news:edition.admin.edit")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t("news:edition.admin.remove")}
                    disabled={users(template.key).length > 0}
                    title={users(template.key).length ? t("news:auto.inUse") : undefined}
                    onClick={() => remove.mutate(template.key)}
                  >
                    <Icon name="trash" size={16} />
                  </Button>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
      <Dialog
        trigger={null}
        open={editing !== null}
        onOpenChange={(open) => (open ? null : setEditing(null))}
        title={editing?.definition.name || t("news:edition.admin.editTemplate")}
        closeLabel={t("news:edition.admin.cancel")}
        size="full"
      >
        {editing ? (
          <TemplateEditor
            key={editing.key ?? "new"}
            start={editing.definition}
            startKey={editing.key}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </Dialog>
    </AdminSection>
  );
}

/** issue 316: every edition written — drafts to read, publish (and e-mail) or delete; what was sent. */
function History() {
  const t = useT();
  const format = useFormat();
  const editions = useAdminEditions();
  const { publish, remove, test } = useEditionActions();
  const [open, setOpen] = useState<string | null>(null);
  const items = editions.data ?? [];
  return (
    <AdminSection icon="list" title={t("news:edition.admin.history")} span="full">
      {test.isSuccess ? (
        <p role="status">{t(test.data ? "news:edition.admin.testSent" : "news:edition.admin.testFailed")}</p>
      ) : test.isError ? (
        <p role="alert">{t("news:edition.admin.testFailed")}</p>
      ) : null}
      {items.length ? (
        <ul className="edition-history">
          {items.map((edition) => (
            <li key={edition.id}>
              <div className="edition-history__row">
                <span className="edition-history__text">
                  <strong>{edition.title}</strong>
                  <small>
                    {format.date(edition.published_at ?? edition.created_at, "medium")} ·{" "}
                    {t("news:edition.admin.daysShort", { count: edition.days })}
                    {edition.emailed_at
                      ? ` · ${t("news:edition.admin.sentTo", { count: edition.recipients })}`
                      : ""}
                  </small>
                </span>
                <StatusBadge tone={edition.status === "published" ? "ok" : "neutral"}>
                  {t(`news:edition.status.${edition.status}`)}
                </StatusBadge>
                <span className="edition-history__actions">
                  <Button
                    variant="ghost"
                    aria-pressed={open === edition.id}
                    onClick={() => setOpen(open === edition.id ? null : edition.id)}
                  >
                    <Icon name="eye" size={16} />
                    {t("news:edition.admin.read")}
                  </Button>
                  {/* issue 317: the real e-mail, without the members — to me alone */}
                  <Button variant="ghost" disabled={test.isPending} onClick={() => test.mutate(edition.id)}>
                    <Icon name="mail" size={16} />
                    {t("news:edition.admin.testMe")}
                  </Button>
                  {!edition.emailed_at ? (
                    <Button onClick={() => publish.mutate({ id: edition.id, email: true })}>
                      <Icon name="send" size={16} />
                      {t("news:edition.admin.publishEmail")}
                    </Button>
                  ) : null}
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t("news:edition.admin.remove")}
                    onClick={() => remove.mutate(edition.id)}
                  >
                    <Icon name="trash" size={16} />
                  </Button>
                </span>
              </div>
              {open === edition.id ? <Preview id={edition.id} title={edition.title} /> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="admin-muted">{t("news:edition.admin.none")}</p>
      )}
    </AdminSection>
  );
}

/**
 * issue 316: the self-writing newsletters, after Ghostarr's principle with the portal's data — every edition
 * written and the templates (look and sections); issue 325: they are written by the automatic newsletters.
 */
export function EditionsAdmin() {
  return (
    <>
      <History />
      <Templates />
    </>
  );
}
