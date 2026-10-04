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

export interface Arrange {
  cell: { x: number; y: number; w: number; h: number };
  index: number;
  count: number;
  prev?: { x: number; y: number; w: number; h: number } | undefined;
  next?: { x: number; y: number; w: number; h: number } | undefined;
  move: (x: number, y: number) => void;
  resize: (w: number, h: number) => void;
}

export function EditControls({
  instance,
  count,
  apply,
  arrange,
}: {
  instance: Instance;
  count: number;
  apply: (change: Change) => void;
  /**
   * Desktop edit session (027 FR-040): the buttons change the draft like a drag would — moving up takes
   * the previous widget's place (reading order), moving down goes below the next one; saved with the rest.
   */
  arrange?: Arrange | undefined;
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
  const cell = arrange?.cell ?? instance;
  const index = arrange?.index ?? instance.position;
  const total = arrange?.count ?? count;
  const resize = (w: number, h: number) => {
    if (arrange) arrange.resize(w, h);
    else patch({ w, h });
    announce(t("dashboard:resized", { title, w, h }));
  };
  const move = (up: boolean) => {
    const neighbour = up ? arrange?.prev : arrange?.next;
    if (arrange && neighbour) {
      if (up) arrange.move(neighbour.x, neighbour.y);
      else arrange.move(neighbour.x, neighbour.y + neighbour.h);
    } else if (!arrange) {
      patch({ position: instance.position + (up ? -1 : 1) });
    }
    announce(t("dashboard:moved", { title, position: index + (up ? 0 : 2) }));
  };
  const fixed = instance.locked;
  return (
    <div className="widget-frame__controls ds-stack ds-stack--row" role="toolbar" aria-label={title}>
      <Button variant="secondary" disabled={fixed || index === 0} onClick={() => move(true)}>
        {t("dashboard:moveUp")}
      </Button>
      <Button variant="secondary" disabled={fixed || index >= total - 1} onClick={() => move(false)}>
        {t("dashboard:moveDown")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || cell.w >= widget.max_w}
        onClick={() => resize(cell.w + 1, cell.h)}
      >
        {t("dashboard:wider")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || cell.w <= widget.min_w}
        onClick={() => resize(cell.w - 1, cell.h)}
      >
        {t("dashboard:narrower")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || cell.h >= widget.max_h}
        onClick={() => resize(cell.w, cell.h + 1)}
      >
        {t("dashboard:taller")}
      </Button>
      <Button
        variant="secondary"
        disabled={fixed || !widget || cell.h <= widget.min_h}
        onClick={() => resize(cell.w, cell.h - 1)}
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
