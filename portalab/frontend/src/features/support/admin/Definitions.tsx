import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../../api/client";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminTabs,
  FormActions,
  FormGrid,
  JsonField,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import type { FieldDef } from "../tickets/api";
import { FieldsBuilder } from "./FieldsBuilder";
import "../support.css";
import "../../gamification/gamification.css";

/**
 * Support configuration (spec 016 T026; 027 redesign, ``support.configure``): **feedback forms** — everyday
 * forms and *requests* asked of members between two dates — and **ticket types** built question by
 * question; workflows (a state machine) stay an advanced JSON document validated by the server.
 */
type Kind = "forms" | "types" | "workflows";
const KEY = ["support", "admin"] as const;
const FORM_KINDS = ["general", "bug_report", "feature_request", "survey", "other"];
const ICONS = [
  "message",
  "star",
  "lightbulb",
  "bug",
  "heart",
  "sparkles",
  "megaphone",
  "film",
  "shop",
  "users",
];

export interface FormRow {
  key: string;
  kind: string;
  label: string;
  fields: FieldDef[];
  enabled: boolean;
  version: number;
  description?: string;
  icon?: string | null;
  requested?: boolean;
  opens_at?: string | null;
  closes_at?: string | null;
}

interface TypeRow {
  key: string;
  label: string;
  workflow_key: string;
  fields: FieldDef[];
  enabled: boolean;
  /** issue 354: the type « Report a problem » on a media's page opens (one at most) */
  media?: boolean;
  version: number;
}

function useList<T>(kind: Kind) {
  return useQuery({
    queryKey: [...KEY, kind],
    retry: false,
    queryFn: async () => {
      if (kind === "types")
        return ((await api.GET("/api/v1/admin/support/types")).data ?? []) as unknown as T[];
      if (kind === "forms")
        return ((await api.GET("/api/v1/admin/support/forms")).data ?? []) as unknown as T[];
      return ((await api.GET("/api/v1/admin/support/workflows")).data ?? []) as unknown as T[];
    },
  });
}

function slug(label: string): string {
  return label
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_")
    .slice(0, 60);
}

const local = (iso?: string | null) => {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

function errorText(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  const errors = error.extensions.errors as string[] | undefined;
  return [error.message, ...(errors ?? [])].join(" — ");
}

export function FormEditor({ form, onDone }: { form?: FormRow; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const [draft, setDraft] = useState<FormRow>(
    form ?? {
      key: "",
      kind: "survey",
      label: "",
      fields: [],
      enabled: true,
      version: 0,
      description: "",
      icon: "message",
      requested: true,
      opens_at: new Date().toISOString(),
      closes_at: new Date(Date.now() + 14 * 86_400_000).toISOString(),
    },
  );
  const patch = (next: Partial<FormRow>) => setDraft({ ...draft, ...next });
  const save = useMutation({
    mutationFn: async () => {
      const { key, version: _v, ...body } = draft;
      const result = await api.PUT("/api/v1/admin/support/forms/{key}", {
        params: { path: { key } },
        body: {
          kind: body.kind,
          label: body.label,
          enabled: body.enabled,
          description: body.description ?? "",
          icon: body.icon ?? null,
          requested: body.requested ?? false,
          fields: body.fields as unknown as Array<Record<string, unknown>>,
          opens_at: body.requested ? (body.opens_at ?? null) : null,
          closes_at: body.requested ? (body.closes_at ?? null) : null,
        },
      });
      return result.data;
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["support"] });
      onDone();
    },
  });
  return (
    <form
      className="admin-form support-builder"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <FormGrid>
        <TextField
          label={t("support:forms.label")}
          required
          maxLength={120}
          value={draft.label}
          onChange={(e) => patch({ label: e.target.value, ...(form ? {} : { key: slug(e.target.value) }) })}
        />
        <SelectField
          label={t("support:forms.kind")}
          value={draft.kind}
          onChange={(e) => patch({ kind: e.target.value })}
        >
          {FORM_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {t(`support:forms.kinds.${kind}`)}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("support:forms.icon")}
          value={draft.icon ?? "message"}
          onChange={(e) => patch({ icon: e.target.value })}
        >
          {ICONS.map((icon) => (
            <option key={icon} value={icon}>
              {icon}
            </option>
          ))}
        </SelectField>
      </FormGrid>
      <TextField
        label={t("support:forms.description")}
        hint={t("support:forms.descriptionHint")}
        maxLength={2000}
        value={draft.description ?? ""}
        onChange={(e) => patch({ description: e.target.value })}
      />
      <fieldset className="gam-fieldset support-request">
        <legend>{t("support:forms.request")}</legend>
        <CheckboxField
          label={t("support:forms.requested")}
          hint={t("support:forms.requestedHint")}
          checked={draft.requested ?? false}
          onChange={(e) => patch({ requested: e.target.checked })}
        />
        {draft.requested ? (
          <FormGrid>
            <TextField
              label={t("support:forms.opens")}
              type="datetime-local"
              value={local(draft.opens_at)}
              onChange={(e) =>
                patch({ opens_at: e.target.value ? new Date(e.target.value).toISOString() : null })
              }
            />
            <TextField
              label={t("support:forms.closes")}
              type="datetime-local"
              value={local(draft.closes_at)}
              onChange={(e) =>
                patch({ closes_at: e.target.value ? new Date(e.target.value).toISOString() : null })
              }
            />
          </FormGrid>
        ) : null}
      </fieldset>
      <fieldset className="gam-fieldset">
        <legend>{t("support:forms.questions")}</legend>
        <FieldsBuilder fields={draft.fields} onChange={(fields) => patch({ fields })} />
      </fieldset>
      <CheckboxField
        label={t("support:forms.enabled")}
        checked={draft.enabled}
        onChange={(e) => patch({ enabled: e.target.checked })}
      />
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {errorText(save.error, t("support:admin.invalid"))}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={!draft.key || !draft.fields.length || save.isPending}>
          <Icon name="check" size={16} />
          {t("support:admin.save")}
        </Button>
      </FormActions>
    </form>
  );
}

function TypeEditor({
  type,
  onDone,
  workflows,
}: {
  type?: TypeRow;
  onDone: () => void;
  workflows: string[];
}) {
  const t = useT();
  const client = useQueryClient();
  const [draft, setDraft] = useState<TypeRow>(
    type ?? {
      key: "",
      label: "",
      workflow_key: workflows[0] ?? "baseline",
      fields: [],
      enabled: true,
      media: false,
      version: 0,
    },
  );
  const patch = (next: Partial<TypeRow>) => setDraft({ ...draft, ...next });
  const save = useMutation({
    mutationFn: async () => {
      const { key, version: _v, ...body } = draft;
      return (
        await api.PUT("/api/v1/admin/support/types/{key}", {
          params: { path: { key } },
          body: {
            ...body,
            media: Boolean(body.media),
            fields: body.fields as unknown as Array<Record<string, unknown>>,
          },
        })
      ).data;
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      onDone();
    },
  });
  return (
    <form
      className="admin-form support-builder"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <FormGrid>
        <TextField
          label={t("support:types.label")}
          required
          maxLength={120}
          value={draft.label}
          onChange={(e) => patch({ label: e.target.value, ...(type ? {} : { key: slug(e.target.value) }) })}
        />
        <SelectField
          label={t("support:types.workflow")}
          value={draft.workflow_key}
          onChange={(e) => patch({ workflow_key: e.target.value })}
        >
          {workflows.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </SelectField>
      </FormGrid>
      <fieldset className="gam-fieldset">
        <legend>{t("support:types.fields")}</legend>
        <FieldsBuilder fields={draft.fields} onChange={(fields) => patch({ fields })} staffOnly />
      </fieldset>
      <CheckboxField
        label={t("support:forms.enabled")}
        checked={draft.enabled}
        onChange={(e) => patch({ enabled: e.target.checked })}
      />
      <CheckboxField
        label={t("support:types.media")}
        hint={t("support:types.mediaHint")}
        checked={Boolean(draft.media)}
        onChange={(e) => patch({ media: e.target.checked })}
      />
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {errorText(save.error, t("support:admin.invalid"))}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={!draft.key || save.isPending}>
          <Icon name="check" size={16} />
          {t("support:admin.save")}
        </Button>
      </FormActions>
    </form>
  );
}

function WorkflowEditor({ itemKey, initial }: { itemKey: string; initial: unknown }) {
  const t = useT();
  const client = useQueryClient();
  const [text, setText] = useState(JSON.stringify(initial, null, 2));
  const save = useMutation({
    mutationFn: async () =>
      (
        await api.PUT("/api/v1/admin/support/workflows/{key}", {
          params: { path: { key: itemKey } },
          body: { definition: JSON.parse(text) as Record<string, unknown> },
        })
      ).data,
    onSettled: () => client.invalidateQueries({ queryKey: KEY }),
  });
  return (
    <div className="admin-form admin-dialog-body">
      <JsonField id={`edit-workflow-${itemKey}`} label={itemKey} value={text} onChange={setText} rows={16} />
      {save.isSuccess ? <p role="status">{t("support:admin.saved")}</p> : null}
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {errorText(save.error, t("support:admin.invalid"))}
        </p>
      ) : null}
      <FormActions>
        <Button onClick={() => save.mutate()}>{t("support:admin.save")}</Button>
      </FormActions>
    </div>
  );
}

function FormsPanel() {
  const t = useT();
  const format = useFormat();
  const forms = useList<FormRow>("forms");
  const [open, setOpen] = useState<string | null>(null);
  const now = Date.now();
  const state = (form: FormRow) => {
    if (!form.enabled) return { tone: "neutral" as const, label: t("support:forms.state.off") };
    if (!form.requested) return { tone: "info" as const, label: t("support:forms.state.everyday") };
    const opens = form.opens_at ? Date.parse(form.opens_at) : 0;
    const closes = form.closes_at ? Date.parse(form.closes_at) : Number.POSITIVE_INFINITY;
    if (now < opens) return { tone: "info" as const, label: t("support:forms.state.planned") };
    if (now >= closes) return { tone: "neutral" as const, label: t("support:forms.state.closed") };
    return { tone: "ok" as const, label: t("support:forms.state.open") };
  };
  return (
    <AdminSection
      span="full"
      icon="message"
      title={t("support:admin.forms")}
      description={t("support:forms.hint")}
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => setOpen(next ? "new" : null)}
          title={t("support:forms.new")}
          closeLabel={t("support:admin.close")}
          size="lg"
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("support:forms.new")}
            </Button>
          }
        >
          <FormEditor onDone={() => setOpen(null)} />
        </Dialog>
      }
    >
      {forms.isError ? <FunctionalState state="unauthorized" /> : null}
      {forms.data && !forms.data.length ? (
        <AdminEmpty icon="message" title={t("support:admin.empty")} />
      ) : null}
      <ul className="gam-cards">
        {(forms.data ?? []).map((form) => {
          const badge = state(form);
          return (
            <li key={form.key} className="gam-card">
              <span className="gam-card__icon" aria-hidden="true">
                <Icon name={form.icon ?? "message"} size={22} />
              </span>
              <div className="gam-card__body">
                <strong>{form.label}</strong>
                <span className="admin-muted">
                  {t(`support:forms.kinds.${form.kind}`)} ·{" "}
                  {t("support:forms.questionCount", { count: form.fields.length })}
                  {form.requested && form.closes_at
                    ? ` · ${t("support:forms.until", { date: format.date(form.closes_at, "medium") })}`
                    : ""}
                </span>
                {form.description ? <span className="admin-muted">{form.description}</span> : null}
              </div>
              <span className="gam-card__actions">
                <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>
                <Dialog
                  open={open === form.key}
                  onOpenChange={(next) => setOpen(next ? form.key : null)}
                  title={form.label}
                  closeLabel={t("support:admin.close")}
                  size="lg"
                  trigger={
                    <Button variant="ghost" aria-label={t("support:admin.edit")}>
                      <Icon name="settings" size={16} />
                    </Button>
                  }
                >
                  <FormEditor form={form} onDone={() => setOpen(null)} />
                </Dialog>
              </span>
            </li>
          );
        })}
      </ul>
    </AdminSection>
  );
}

function TypesPanel() {
  const t = useT();
  const types = useList<TypeRow>("types");
  const workflows = useList<{ key: string }>("workflows");
  const [open, setOpen] = useState<string | null>(null);
  const keys = [...new Set((workflows.data ?? []).map((w) => w.key))];
  return (
    <AdminSection
      span="full"
      icon="ticket"
      title={t("support:admin.types")}
      description={t("support:types.hint")}
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => setOpen(next ? "new" : null)}
          title={t("support:types.new")}
          closeLabel={t("support:admin.close")}
          size="lg"
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("support:types.new")}
            </Button>
          }
        >
          <TypeEditor workflows={keys} onDone={() => setOpen(null)} />
        </Dialog>
      }
    >
      <ul className="gam-cards">
        {(types.data ?? []).map((type) => (
          <li key={type.key} className="gam-card">
            <span className="gam-card__icon" aria-hidden="true">
              <Icon name="ticket" size={22} />
            </span>
            <div className="gam-card__body">
              <strong>{type.label}</strong>
              <span className="admin-muted">
                {t("support:forms.questionCount", { count: type.fields.length })} · {type.workflow_key}
              </span>
            </div>
            <span className="gam-card__actions">
              {type.media ? <StatusBadge tone="info">{t("support:types.mediaBadge")}</StatusBadge> : null}
              {!type.enabled ? (
                <StatusBadge tone="neutral">{t("support:forms.state.off")}</StatusBadge>
              ) : null}
              <Dialog
                open={open === type.key}
                onOpenChange={(next) => setOpen(next ? type.key : null)}
                title={type.label}
                closeLabel={t("support:admin.close")}
                size="lg"
                trigger={
                  <Button variant="ghost" aria-label={t("support:admin.edit")}>
                    <Icon name="settings" size={16} />
                  </Button>
                }
              >
                <TypeEditor type={type} workflows={keys} onDone={() => setOpen(null)} />
              </Dialog>
            </span>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}

function WorkflowsPanel() {
  const t = useT();
  const workflows = useList<{ key: string; version: number; definition: unknown }>("workflows");
  const latest = new Map<string, { key: string; version: number; definition: unknown }>();
  for (const w of workflows.data ?? []) {
    const current = latest.get(w.key);
    if (!current || current.version < w.version) latest.set(w.key, w);
  }
  return (
    <AdminSection
      span="full"
      icon="list"
      title={t("support:admin.workflows")}
      description={t("support:workflows.hint")}
    >
      <ul className="gam-cards">
        {[...latest.values()].map((w) => (
          <li key={w.key} className="gam-card">
            <span className="gam-card__icon" aria-hidden="true">
              <Icon name="list" size={22} />
            </span>
            <div className="gam-card__body">
              <strong>{w.key}</strong>
              <span className="admin-muted">v{w.version}</span>
            </div>
            <span className="gam-card__actions">
              <Dialog
                size="lg"
                title={w.key}
                closeLabel={t("support:admin.close")}
                trigger={
                  <Button variant="ghost" aria-label={t("support:admin.edit")}>
                    <Icon name="settings" size={16} />
                  </Button>
                }
              >
                <WorkflowEditor key={`${w.key}-${w.version}`} itemKey={w.key} initial={w.definition} />
              </Dialog>
            </span>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}

export function Definitions() {
  const t = useT();
  const [kind, setKind] = useState<Kind>("forms");
  return (
    <AdminPage
      icon="lifebuoy"
      title={t("support:admin.title")}
      description={t("support:admin.description")}
      tabs={
        <AdminTabs
          label={t("support:admin.title")}
          current={kind}
          onChange={(k) => setKind(k as Kind)}
          tabs={(["forms", "types", "workflows"] as Kind[]).map((k) => ({
            key: k,
            label: t(`support:admin.${k}`),
          }))}
        />
      }
    >
      {kind === "forms" ? <FormsPanel /> : null}
      {kind === "types" ? <TypesPanel /> : null}
      {kind === "workflows" ? <WorkflowsPanel /> : null}
    </AdminPage>
  );
}

export default Definitions;
