import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { useAnnounce } from "../../../design-system/a11y/Announce";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import type { Change, Instance } from "../api";

/**
 * Edit controls of one widget (spec 009 T019; 027): moving and resizing are done on the grid itself (drag
 * the grip or pull the edges; keyboard: Enter on the grip then arrows, Shift + arrows to resize), so a
 * widget only keeps two buttons in its header — its settings and « remove ». Policy-locked actions are
 * disabled with their reason; the server enforces them anyway.
 */
interface SchemaProperty {
  type?: string;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  maxLength?: number;
}

export function EditControls({ instance, apply }: { instance: Instance; apply: (change: Change) => void }) {
  const t = useT();
  const announce = useAnnounce();
  const widget = instance.widget;
  const id = instance.id;
  const title = widget ? t(widget.title_key) : instance.widget_key;
  if (!id) return null; // synthesized by a policy: nothing to personalize
  const configurable =
    widget && !instance.locked && Object.keys((widget.config_schema.properties as object) ?? {}).length > 0;
  return (
    <div className="widget-frame__controls" role="toolbar" aria-label={title}>
      {configurable ? (
        <ConfigDialog
          instance={instance}
          onSave={(config) => apply({ kind: "patch", id, body: { config } })}
        />
      ) : null}
      <Button
        variant="danger"
        disabled={!instance.removable}
        onClick={() => {
          apply({ kind: "remove", id });
          announce(t("dashboard:removed", { title }));
        }}
        size="icon"
        aria-label={t("dashboard:remove")}
        title={instance.removable ? t("dashboard:remove") : t("dashboard:mandatory")}
      >
        <Icon name="trash" size={16} />
      </Button>
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
  // 027: settings sold in the shop (another chart, a longer period…) stay visible, locked
  const lockedOptions = useQuery({
    queryKey: ["dashboard", "locked-options"],
    enabled: open,
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/dashboard/locked-options")).data as unknown as { locked: string[] }).locked,
  });
  const isLocked = (name: string, option: unknown) =>
    Boolean(lockedOptions.data?.includes(`${instance.widget_key}:${name}=${String(option)}`));
  const hasLocked = Object.entries(properties).some(([name, schema]) =>
    (schema.enum ?? []).some((option) => isLocked(name, option)),
  );
  // 027: labels from the widget's catalog (« <ns>:widget.<name>.config.<field>[.<option>] »), else raw
  const [ns, ...rest] = instance.widget_key.split(".");
  const base = `${ns}:widget.${rest.join(".")}.config`;
  const label = (key: string, fallback: string) => {
    const text = t(key);
    return text === key.split(":").slice(1).join(":") ? fallback : text;
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setDraft(instance.config);
      }}
      title={t("dashboard:settings")}
      closeLabel={t("dashboard:cancel")}
      trigger={
        <Button
          variant="secondary"
          size="icon"
          aria-label={t("dashboard:settings")}
          title={t("dashboard:settings")}
        >
          <Icon name="settings" size={16} />
        </Button>
      }
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
                label={label(`${base}.${name}`, name)}
                value={String(value ?? "")}
                onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
              >
                {schema.enum.map((option) => (
                  <option key={String(option)} value={String(option)} disabled={isLocked(name, option)}>
                    {isLocked(name, option) ? "🔒 " : ""}
                    {label(`${base}.${name}.${String(option)}`, String(option))}
                    {isLocked(name, option) ? ` · ${t("dashboard:inShop")}` : ""}
                  </option>
                ))}
              </SelectField>
            );
          if (schema.type === "boolean")
            return (
              <CheckboxField
                key={name}
                label={label(`${base}.${name}`, name)}
                checked={Boolean(value)}
                onChange={(e) => setDraft({ ...draft, [name]: e.target.checked })}
              />
            );
          if (schema.type === "integer" || schema.type === "number")
            return (
              <TextField
                key={name}
                label={label(`${base}.${name}`, name)}
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
              label={label(`${base}.${name}`, name)}
              value={String(value ?? "")}
              maxLength={schema.maxLength ?? 200}
              onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
            />
          );
        })}
        <CheckboxField
          label={t("dashboard:hideWhenEmpty")}
          hint={t("dashboard:hideWhenEmptyHint")}
          checked={Boolean(draft._hide_empty)}
          onChange={(e) => setDraft({ ...draft, _hide_empty: e.target.checked })}
        />
        {hasLocked ? (
          <p className="ds-field__hint">
            <Link to="/marketplace?type=widget_option">{t("dashboard:moreOptions")}</Link>
          </p>
        ) : null}
        <Button type="submit">{t("dashboard:save")}</Button>
      </form>
    </Dialog>
  );
}
