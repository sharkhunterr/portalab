import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { AdminPage, AdminSection, FormActions, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import "../dashboard.css";

/**
 * Members' dashboard (027, ``dashboard.manage``): what every dashboard shows. Each widget has a policy —
 * free, offered by default, required, locked, **pinned** (always there, at a place chosen here) or
 * disabled — and the starter dashboard is the one a first visit (or « Default ») gets, in rows of 12.
 */
type Policy = { class: string; x?: number; y?: number; w?: number; h?: number; [key: string]: unknown };
interface WidgetInfo {
  key: string;
  title_key: string;
  icon?: string | null;
  sold?: boolean;
  size?: { default: { w: number; h: number }; min: { w: number; h: number }; max: { w: number; h: number } };
}
interface Settings {
  policies: Record<string, Policy>;
  starter: Array<{ widget_key: string; w: number; h: number; roles?: string[] }>;
  widgets: WidgetInfo[];
}

const CLASSES = ["free", "default", "mandatory", "locked", "pinned", "disabled"];
const KEY = ["admin", "dashboard"] as const;

/** A policy without the place fields (only a pinned widget has a place). */
function withoutPlace(policy: Policy): Policy {
  const { x: _x, y: _y, w: _w, h: _h, move: _move, resize: _resize, ...rest } = policy;
  return rest as Policy;
}

function errorText(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  const errors = error.extensions.errors as string[] | undefined;
  return [error.message, ...(errors ?? [])].join(" — ");
}

/** The 12-column first rows with the pinned widgets drawn where they sit. */
function PinPreview({ pins, titleOf }: { pins: Array<[string, Policy]>; titleOf: (key: string) => string }) {
  const t = useT();
  const rows = Math.max(2, ...pins.map(([, p]) => (p.y ?? 0) + (p.h ?? 2)));
  return (
    <div
      className="pin-preview"
      role="img"
      aria-label={t("dashboard:admin.preview")}
      style={{ gridTemplateRows: `repeat(${rows}, 1.6rem)` }}
    >
      {pins.map(([key, p]) => (
        <span
          key={key}
          className="pin-preview__item"
          style={{
            gridColumn: `${(p.x ?? 0) + 1} / span ${p.w ?? 6}`,
            gridRow: `${(p.y ?? 0) + 1} / span ${p.h ?? 2}`,
          }}
        >
          <Icon name="lock" size={12} /> {titleOf(key)}
        </span>
      ))}
    </div>
  );
}

export default function DashboardAdmin() {
  const t = useT();
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: KEY,
    queryFn: async () => (await api.GET("/api/v1/admin/dashboard/policies")).data as unknown as Settings,
  });
  const [policies, setPolicies] = useState<Record<string, Policy>>({});
  const [starter, setStarter] = useState<Settings["starter"]>([]);
  const [saved, setSaved] = useState<string | null>(null);
  useEffect(() => {
    if (settings.data) {
      setPolicies(settings.data.policies ?? {});
      setStarter(settings.data.starter ?? []);
    }
  }, [settings.data]);
  const savePolicies = useMutation({
    mutationFn: async () => api.PUT("/api/v1/admin/dashboard/policies", { body: policies as never }),
    onSuccess: () => {
      setSaved("policies");
      void client.invalidateQueries({ queryKey: KEY });
    },
  });
  const saveStarter = useMutation({
    mutationFn: async () => api.PUT("/api/v1/admin/dashboard/starter", { body: starter as never }),
    onSuccess: () => {
      setSaved("starter");
      void client.invalidateQueries({ queryKey: KEY });
    },
  });
  if (!settings.data) return <FunctionalState state={settings.isError ? "unauthorized" : "loading"} />;
  const widgets = [...settings.data.widgets].sort((a, b) => t(a.title_key).localeCompare(t(b.title_key)));
  const titleOf = (key: string) => {
    const found = settings.data.widgets.find((w) => w.key === key);
    return found ? t(found.title_key) : key;
  };
  const set = (key: string, next: Policy | null) => {
    setSaved(null);
    const copy = { ...policies };
    if (next === null || next.class === "free") delete copy[key];
    else copy[key] = next;
    setPolicies(copy);
  };
  const pins = Object.entries(policies).filter(([, p]) => p.class === "pinned");
  const spare = widgets.filter((w) => !starter.some((s) => s.widget_key === w.key));
  return (
    <AdminPage
      icon="dashboard"
      title={t("dashboard:admin.title")}
      description={t("dashboard:admin.description")}
      wide
    >
      <AdminSection
        span="full"
        icon="lock"
        title={t("dashboard:admin.policies")}
        description={t("dashboard:admin.policiesHint")}
      >
        {pins.length ? <PinPreview pins={pins} titleOf={titleOf} /> : null}
        <ul className="dashboard-policies">
          {widgets.map((widget) => {
            const policy = policies[widget.key] ?? { class: "free" };
            return (
              <li key={widget.key} className="dashboard-policy" data-class={policy.class}>
                <span className="dashboard-policy__name">
                  <Icon name={widget.icon ?? "dashboard"} size={18} />
                  <span>
                    <strong>{t(widget.title_key)}</strong>
                    <span className="admin-muted">
                      {widget.key}
                      {widget.sold ? ` · ${t("dashboard:admin.sold")}` : ""}
                    </span>
                  </span>
                </span>
                <SelectField
                  label={t("dashboard:admin.policy")}
                  value={policy.class}
                  onChange={(e) => {
                    const cls = e.target.value;
                    set(
                      widget.key,
                      cls === "pinned"
                        ? {
                            class: "pinned",
                            x: 0,
                            y: Math.max(0, ...pins.map(([, p]) => (p.y ?? 0) + (p.h ?? 2))),
                            w: widget.size?.default.w ?? 6,
                            h: widget.size?.default.h ?? 2,
                          }
                        : withoutPlace({ ...(policies[widget.key] ?? {}), class: cls }),
                    );
                  }}
                >
                  {CLASSES.map((cls) => (
                    <option key={cls} value={cls}>
                      {t(`dashboard:admin.class.${cls}`)}
                    </option>
                  ))}
                </SelectField>
                {policy.class === "pinned" ? (
                  <span className="dashboard-policy__place">
                    {(["x", "y", "w", "h"] as const).map((field) => (
                      <TextField
                        key={field}
                        label={t(`dashboard:admin.place.${field}`)}
                        type="number"
                        min={field === "w" || field === "h" ? 1 : 0}
                        max={field === "x" ? 11 : 12}
                        value={String(policy[field] ?? 0)}
                        onChange={(e) => set(widget.key, { ...policy, [field]: Number(e.target.value) })}
                      />
                    ))}
                    {/* 027: what members may still do with it — it never leaves their dashboard */}
                    <CheckboxField
                      label={t("dashboard:admin.allowMove")}
                      checked={Boolean(policy.move)}
                      onChange={(e) => set(widget.key, { ...policy, move: e.target.checked })}
                    />
                    <CheckboxField
                      label={t("dashboard:admin.allowResize")}
                      checked={Boolean(policy.resize)}
                      onChange={(e) => set(widget.key, { ...policy, resize: e.target.checked })}
                    />
                  </span>
                ) : (
                  <span className="admin-muted dashboard-policy__hint">
                    {t(`dashboard:admin.classHint.${policy.class}`)}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        {savePolicies.isError ? (
          <p role="alert" className="services-admin__ko">
            {errorText(savePolicies.error, t("dashboard:admin.failed"))}
          </p>
        ) : null}
        {saved === "policies" ? <p role="status">{t("dashboard:admin.saved")}</p> : null}
        <FormActions>
          <Button disabled={savePolicies.isPending} onClick={() => savePolicies.mutate()}>
            <Icon name="check" size={16} />
            {t("dashboard:admin.save")}
          </Button>
        </FormActions>
      </AdminSection>

      <AdminSection
        span="full"
        icon="sparkles"
        title={t("dashboard:admin.starter")}
        description={t("dashboard:admin.starterHint")}
      >
        <ol className="dashboard-starter">
          {starter.map((entry, index) => {
            const info = settings.data.widgets.find((w) => w.key === entry.widget_key);
            return (
              <li key={entry.widget_key} className="dashboard-starter__row">
                <span className="dashboard-starter__bar" style={{ inlineSize: `${(entry.w / 12) * 100}%` }}>
                  <Icon name={info?.icon ?? "dashboard"} size={14} /> {titleOf(entry.widget_key)}
                </span>
                <TextField
                  label={t("dashboard:admin.place.w")}
                  type="number"
                  min={info?.size?.min.w ?? 1}
                  max={info?.size?.max.w ?? 12}
                  value={String(entry.w)}
                  onChange={(e) =>
                    setStarter(starter.map((s, i) => (i === index ? { ...s, w: Number(e.target.value) } : s)))
                  }
                />
                <TextField
                  label={t("dashboard:admin.place.h")}
                  type="number"
                  min={info?.size?.min.h ?? 1}
                  max={info?.size?.max.h ?? 12}
                  value={String(entry.h)}
                  onChange={(e) =>
                    setStarter(starter.map((s, i) => (i === index ? { ...s, h: Number(e.target.value) } : s)))
                  }
                />
                <span className="dashboard-starter__tools">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t("dashboard:admin.up")}
                    disabled={index === 0}
                    onClick={() => {
                      const next = [...starter];
                      [next[index - 1], next[index]] = [
                        next[index] as typeof entry,
                        next[index - 1] as typeof entry,
                      ];
                      setStarter(next);
                    }}
                  >
                    <Icon name="arrow-up" size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t("dashboard:admin.remove")}
                    onClick={() => setStarter(starter.filter((_, i) => i !== index))}
                  >
                    <Icon name="trash" size={16} />
                  </Button>
                </span>
              </li>
            );
          })}
        </ol>
        {spare.length ? (
          <SelectField
            label={t("dashboard:admin.add")}
            value=""
            onChange={(e) => {
              const info = settings.data.widgets.find((w) => w.key === e.target.value);
              if (info)
                setStarter([
                  ...starter,
                  { widget_key: info.key, w: info.size?.default.w ?? 6, h: info.size?.default.h ?? 3 },
                ]);
            }}
          >
            <option value="">—</option>
            {spare.map((w) => (
              <option key={w.key} value={w.key}>
                {t(w.title_key)}
              </option>
            ))}
          </SelectField>
        ) : null}
        <p className="admin-muted">
          <StatusBadge tone="info">{t("dashboard:admin.tip")}</StatusBadge> {t("dashboard:admin.tipText")}
        </p>
        {saveStarter.isError ? (
          <p role="alert" className="services-admin__ko">
            {errorText(saveStarter.error, t("dashboard:admin.failed"))}
          </p>
        ) : null}
        {saved === "starter" ? <p role="status">{t("dashboard:admin.saved")}</p> : null}
        <FormActions>
          <Button disabled={saveStarter.isPending} onClick={() => saveStarter.mutate()}>
            <Icon name="check" size={16} />
            {t("dashboard:admin.save")}
          </Button>
        </FormActions>
      </AdminSection>
    </AdminPage>
  );
}
