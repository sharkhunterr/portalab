import { useState } from "react";
import { useAnnounce } from "../../../design-system/a11y/Announce";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import type { Change, Instance } from "../api";

/**
 * Edit controls of one widget (spec 009 T019; R4, WCAG 2.2): every personalization — move, resize, hide,
 * remove, configure — is a plain button (keyboard and touch; never drag-only). Policy-locked actions are
 * disabled with their reason; the server enforces them anyway.
 */
interface SchemaProperty {
  type?: string;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  maxLength?: number;
}

export function EditControls({
  instance,
  count,
  apply,
}: {
  instance: Instance;
  count: number;
  apply: (change: Change) => void;
}) {
  const t = useT();
  const announce = useAnnounce();
  const widget = instance.widget;
  const id = instance.id;
  const title = widget ? t(widget.title_key) : instance.widget_key;
  if (!id) return null; // synthesized by a policy: nothing to personalize
  const patch = (body: Extract<Change, { kind: "patch" }>["body"], message?: string) => {
    apply({ kind: "patch", id, body });
    if (message) announce(message);
  };
  const resize = (w: number, h: number) => patch({ w, h }, t("dashboard:resized", { title, w, h }));
  const move = (position: number) =>
    patch({ position }, t("dashboard:moved", { title, position: position + 1 }));
  const fixed = instance.locked;
  return (
    <div className="widget-frame__controls ds-stack ds-stack--row" role="toolbar" aria-label={title}>
      <Button
        variant="secondary"
        disabled={fixed || instance.position === 0}
        onClick={() => move(instance.position - 1)}
      >
        {t("dashboard:moveUp")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || instance.position >= count - 1}
        onClick={() => move(instance.position + 1)}
      >
        {t("dashboard:moveDown")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || instance.w >= widget.max_w}
        onClick={() => resize(instance.w + 1, instance.h)}
      >
        {t("dashboard:wider")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || instance.w <= widget.min_w}
        onClick={() => resize(instance.w - 1, instance.h)}
      >
        {t("dashboard:narrower")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || instance.h >= widget.max_h}
        onClick={() => resize(instance.w, instance.h + 1)}
      >
        {t("dashboard:taller")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || instance.h <= widget.min_h}
        onClick={() => resize(instance.w, instance.h - 1)}
      >
        {t("dashboard:shorter")}
      </Button>
      {widget && !fixed && Object.keys((widget.config_schema.properties as object) ?? {}).length ? (
        <ConfigDialog instance={instance} onSave={(config) => patch({ config })} />
      ) : null}
      <Button variant="secondary" disabled={!instance.hideable} onClick={() => patch({ status: "hidden" })}>
        {t("dashboard:hide")}
      </Button>
      <Button variant="danger" disabled={!instance.removable} onClick={() => apply({ kind: "remove", id })}>
        {t("dashboard:remove")}
      </Button>
      {!instance.hideable ? <span className="widget__meta">{t("dashboard:mandatory")}</span> : null}
    </div>
  );
}

function ConfigDialog({
  instance,
  onSave,
}: {
  instance: Instance;
  onSave: (config: Record<string, unknown>) => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>(instance.config);
  const properties = (instance.widget?.config_schema.properties ?? {}) as Record<string, SchemaProperty>;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setDraft(instance.config);
      }}
      title={t("dashboard:settings")}
      closeLabel={t("dashboard:cancel")}
      trigger={<Button variant="secondary">{t("dashboard:settings")}</Button>}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave(draft);
          setOpen(false);
        }}
      >
        {Object.entries(properties).map(([name, schema]) => {
          const value = draft[name];
          if (schema.enum)
            return (
              <SelectField
                key={name}
                label={name}
                value={String(value ?? "")}
                onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
              >
                {schema.enum.map((option) => (
                  <option key={String(option)} value={String(option)}>
                    {String(option)}
                  </option>
                ))}
              </SelectField>
            );
          if (schema.type === "boolean")
            return (
              <CheckboxField
                key={name}
                label={name}
                checked={Boolean(value)}
                onChange={(e) => setDraft({ ...draft, [name]: e.target.checked })}
              />
            );
          if (schema.type === "integer" || schema.type === "number")
            return (
              <TextField
                key={name}
                label={name}
                type="number"
                value={String(value ?? "")}
                {...(schema.minimum !== undefined ? { min: schema.minimum } : {})}
                {...(schema.maximum !== undefined ? { max: schema.maximum } : {})}
                onChange={(e) => setDraft({ ...draft, [name]: Number(e.target.value) })}
              />
            );
          return (
            <TextField
              key={name}
              label={name}
              value={String(value ?? "")}
              maxLength={schema.maxLength ?? 200}
              onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
            />
          );
        })}
        <Button type="submit">{t("dashboard:save")}</Button>
      </form>
    </Dialog>
  );
}
