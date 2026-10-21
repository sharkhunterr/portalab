import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { useAnnounce } from "../../../design-system/a11y/Announce";
import { Button } from "../../../design-system/components/Button";
import {
  CheckboxField,
  SelectField,
  TextAreaField,
  TextField,
} from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { externalLooks, useExternalRevision } from "../../../design-system/visuals/registry";
import { useT } from "../../../i18n/hooks/useT";
import type { Change, Instance } from "../api";
import { addonsFor } from "../widgets/pack/WidgetAddons";

/**
 * Edit controls of one widget (spec 009 T019; 027): moving and resizing are done on the grid itself (drag
 * the grip or pull the edges; keyboard: Enter on the grip then arrows, Shift + arrows to resize), so a
 * widget keeps two buttons beside its grip, drawn alike — its settings (always: at least how it is shown)
 * and « remove ». Policy-locked actions are disabled with their reason; the server enforces them anyway.
 */
interface SchemaProperty {
  type?: string;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  maxLength?: number;
  /** 027: the options come from the portal (``services``: the services, by name). */
  "x-options"?: string;
  format?: string;
}

export function EditControls({ instance, apply }: { instance: Instance; apply: (change: Change) => void }) {
  const t = useT();
  const announce = useAnnounce();
  const widget = instance.widget;
  const id = instance.id;
  const title = widget ? t(widget.title_key) : instance.widget_key;
  if (!id) return null; // synthesized by a policy: nothing to personalize
  // 027: every widget has settings — at least how it is displayed (title, box, hidden when empty)
  return (
    <div className="widget-frame__controls" role="toolbar" aria-label={title}>
      <ConfigDialog
        instance={instance}
        disabled={Boolean(instance.locked)}
        onSave={(config) => apply({ kind: "patch", id, body: { config } })}
      />
      <Button
        variant="ghost"
        className="dash-tool ds-button--quiet-danger"
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
  disabled = false,
}: {
  instance: Instance;
  onSave: (config: Record<string, unknown>) => void;
  disabled?: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>(instance.config);
  const properties = (instance.widget?.config_schema.properties ?? {}) as Record<string, SchemaProperty>;
  // 027: a setting offering the services (« which service ») lists them by name
  const services = useQuery({
    queryKey: ["services", "health", "names"],
    enabled: open && Object.values(properties).some((p) => p["x-options"] === "services"),
    staleTime: 60_000,
    queryFn: async () =>
      (
        (await api.GET("/api/v1/services/health")).data as unknown as {
          items: Array<{ id: string; name: string }>;
        }
      ).items,
  });
  // 027: settings sold in the shop (another chart, a longer period…) stay visible, locked
  const lockedOptions = useQuery({
    queryKey: ["dashboard", "locked-options"],
    enabled: open,
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/dashboard/locked-options")).data as unknown as { locked: string[] }).locked,
  });
  const isLocked = (name: string, option: unknown) =>
    Boolean(
      lockedOptions.data?.includes(`${instance.widget_key}:${name}=${String(option)}`) ||
        // 028: a pack's widget style is sold for every widget
        lockedOptions.data?.includes(`*:${name}=${String(option)}`),
    );
  // 028: the frame's looks the live packs bring
  useExternalRevision();
  const addons = addonsFor(instance.widget_key);
  const wornOptions = Array.isArray(draft._options) ? (draft._options as string[]) : [];
  // issue 189: a pack's add-on aimed at this very widget is one of its looks — chosen in « Visual » with
  // the widget's own, one at a time; an add-on for every widget (a decoration) stays a box to tick
  const packLooks = addons.filter((addon) => addon.widget?.for === instance.widget_key && addon.look);
  const decorations = addons.filter((addon) => addon.widget?.for !== instance.widget_key);
  const wornLook = packLooks.find((addon) => wornOptions.includes(addon.look ?? ""))?.look ?? null;
  const lookLocked = (look: string) => isLocked("_options", look) && wornLook !== look;
  const styles = properties.style?.enum?.map(String) ?? null;
  const pickVisual = (value: string) => {
    const others = wornOptions.filter((x) => !packLooks.some((addon) => addon.look === x));
    if (value.startsWith("pack:"))
      setDraft({
        ...draft,
        ...(styles ? { style: styles[0] } : {}), // the widget's own look under it: its first (classic)
        _options: [...others, value.slice("pack:".length)],
      });
    else setDraft({ ...draft, ...(styles ? { style: value } : {}), _options: others });
  };
  const packOptions = packLooks.map((addon) => {
    const look = addon.look ?? "";
    return (
      <option key={`pack:${look}`} value={`pack:${look}`} disabled={lookLocked(look)}>
        {lookLocked(look) ? "🔒 " : ""}
        {t(`dashboard:packOption.${look}`)}
        {lookLocked(look) ? ` · ${t("dashboard:inShop")}` : ""}
      </option>
    );
  });
  const skins = externalLooks("widget_style").filter(
    (skin) => !skin.widget?.for || skin.widget.for === instance.widget_key,
  );
  const hasLocked =
    Object.entries(properties).some(([name, schema]) =>
      (schema.enum ?? []).some((option) => isLocked(name, option)),
    ) ||
    skins.some((skin) => isLocked("_skin", skin.look)) ||
    addons.some((addon) => isLocked("_options", addon.look));
  // 027: labels from the widget's catalog (« <ns>:widget.<name>.config.<field>[.<option>] »), else raw
  const [ns, ...rest] = instance.widget_key.split(".");
  const base = `${ns}:widget.${rest.join(".")}.config`;
  const label = (key: string, fallback: string) => {
    const text = t(key);
    if (text !== key.split(":").slice(1).join(":")) return text;
    // 027 (#31): « style » (a widget's other looks) is named once for every widget
    const shared = key.replace(`${base}.style`, "dashboard:style");
    if (shared !== key) {
      const common = t(shared === "dashboard:style" ? "dashboard:style.title" : shared);
      if (!common.startsWith("style.")) return common;
    }
    // 027: the usual settings (kind, scope, period…) are named once for every widget
    const usual = key.replace(`${base}.`, "dashboard:field.");
    if (usual !== key) {
      const common = t(usual);
      if (common !== usual.split(":").slice(1).join(":")) return common;
    }
    return fallback;
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
          variant="ghost"
          size="icon"
          className="dash-tool"
          disabled={disabled}
          aria-label={t("dashboard:settings")}
          title={disabled ? t("dashboard:locked") : t("dashboard:settings")}
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
          if (schema["x-options"] === "services")
            return (
              <SelectField
                key={name}
                label={label(`${base}.${name}`, name)}
                value={String(value ?? "")}
                onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
              >
                <option value="">{t("dashboard:field.service.auto")}</option>
                {(services.data ?? []).map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name}
                  </option>
                ))}
              </SelectField>
            );
          if (name === "style" && schema.enum && packLooks.length)
            return (
              <SelectField
                key={name}
                label={label(`${base}.${name}`, name)}
                value={wornLook ? `pack:${wornLook}` : String(value ?? "")}
                onChange={(e) => pickVisual(e.target.value)}
              >
                {schema.enum.map((option) => (
                  <option key={String(option)} value={String(option)} disabled={isLocked(name, option)}>
                    {isLocked(name, option) ? "🔒 " : ""}
                    {label(`${base}.${name}.${String(option)}`, String(option))}
                    {isLocked(name, option) ? ` · ${t("dashboard:inShop")}` : ""}
                  </option>
                ))}
                {packOptions}
              </SelectField>
            );
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
          if ((schema.maxLength ?? 0) > 120)
            return (
              <TextAreaField
                key={name}
                label={label(`${base}.${name}`, name)}
                value={String(value ?? "")}
                maxLength={schema.maxLength}
                rows={4}
                onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
              />
            );
          return (
            <TextField
              key={name}
              label={label(`${base}.${name}`, name)}
              type={schema.format === "date" ? "date" : "text"}
              value={String(value ?? "")}
              maxLength={schema.maxLength ?? 200}
              onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
            />
          );
        })}
        {!styles && packLooks.length ? (
          // a widget without looks of its own: « Visual » holds its classic one and the packs'
          <SelectField
            label={label(`${base}.style`, "style")}
            value={wornLook ? `pack:${wornLook}` : ""}
            onChange={(e) => pickVisual(e.target.value)}
          >
            <option value="">{label(`${base}.style.classic`, "classic")}</option>
            {packOptions}
          </SelectField>
        ) : null}
        <fieldset className="widget-config__frame">
          <legend>{t("dashboard:frame.options")}</legend>
          <CheckboxField
            label={t("dashboard:frame.hideTitle")}
            hint={t("dashboard:frame.hideTitleHint")}
            checked={Boolean(draft._hide_title)}
            onChange={(e) => setDraft({ ...draft, _hide_title: e.target.checked })}
          />
          <CheckboxField
            label={t("dashboard:frame.noBox")}
            hint={t("dashboard:frame.noBoxHint")}
            checked={Boolean(draft._no_box)}
            onChange={(e) => setDraft({ ...draft, _no_box: e.target.checked })}
          />
          {skins.length ? (
            <SelectField
              label={t("dashboard:frame.skin")}
              hint={t("dashboard:frame.skinHint")}
              value={typeof draft._skin === "string" ? draft._skin : ""}
              onChange={(e) => setDraft({ ...draft, _skin: e.target.value })}
            >
              <option value="">{t("dashboard:frame.skinNone")}</option>
              {skins.map((skin) => (
                <option key={skin.look} value={skin.look ?? ""} disabled={isLocked("_skin", skin.look)}>
                  {isLocked("_skin", skin.look) ? "🔒 " : ""}
                  {t(`dashboard:packStyle.${skin.look}`)}
                  {isLocked("_skin", skin.look) ? ` · ${t("dashboard:inShop")}` : ""}
                </option>
              ))}
            </SelectField>
          ) : null}
          {decorations.map((addon) => {
            const look = addon.look ?? "";
            const locked = isLocked("_options", look) && !wornOptions.includes(look);
            return (
              <CheckboxField
                key={look}
                label={`${locked ? "🔒 " : ""}${t(`dashboard:packOption.${look}`)}${locked ? ` · ${t("dashboard:inShop")}` : ""}`}
                hint={t("dashboard:frame.addonHint")}
                disabled={locked}
                checked={wornOptions.includes(look)}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    _options: e.target.checked
                      ? [...new Set([...wornOptions, look])]
                      : wornOptions.filter((x) => x !== look),
                  })
                }
              />
            );
          })}
          <CheckboxField
            label={t("dashboard:hideWhenEmpty")}
            hint={t("dashboard:hideWhenEmptyHint")}
            checked={Boolean(draft._hide_empty)}
            onChange={(e) => setDraft({ ...draft, _hide_empty: e.target.checked })}
          />
        </fieldset>
        {hasLocked ? (
          <p className="ds-field__hint">
            <Link to="/marketplace?type=widget_option">{t("dashboard:moreOptions")}</Link>
          </p>
        ) : null}
        <DialogActions>
          <Button type="submit">{t("dashboard:save")}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
