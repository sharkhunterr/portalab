import { useEffect, useState } from "react";
import { AdminSection, FormActions, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useRules } from "../api";
import { MemberStreaks } from "./MemberStreaks";
import { actionLabel, type StreakConfig, useEventTypes, useStreak, VALUES } from "./tuning";

const SUGGESTED = ["media.playback_finished"];

function multiplierAt(tiers: StreakConfig["tiers"], days: number): number {
  return Math.max(1, ...tiers.filter((tier) => days >= tier.days).map((tier) => tier.multiplier));
}

/**
 * Play streaks (027): consecutive days on which a member does one of the counted actions (by default:
 * finishing a film or an episode). Each tier multiplies the rewards of those actions — e.g. ×1.5 from 2
 * days in a row, ×2 from 5 days; one missed day and the streak starts over.
 */
export function StreakPanel() {
  const t = useT();
  const { query, save } = useStreak();
  const types = useEventTypes();
  const rules = useRules();
  const [draft, setDraft] = useState<StreakConfig | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (query.data) setDraft(query.data);
  }, [query.data]);
  if (query.isPending || !draft) return <FunctionalState state="loading" />;
  const patch = (next: Partial<StreakConfig>) => {
    setSaved(false);
    setDraft({ ...draft, ...next });
  };
  const tiers = draft.tiers;
  const ordered = [...tiers].sort((a, b) => a.days - b.days);
  const horizon = Math.max(7, ...tiers.map((tier) => tier.days + 2));
  // the actions that already earn something come first; every other action is one click away
  const rewarded = new Set([
    ...SUGGESTED,
    ...draft.event_types,
    ...(rules.data ?? []).filter((r) => r.status === "active").map((r) => r.event_type),
  ]);
  const names = (types.data ?? []).map((type) => type.name).sort();
  const counted = names.filter((name) => rewarded.has(name));
  const others = names.filter((name) => !rewarded.has(name));
  const box = (name: string) => (
    <CheckboxField
      key={name}
      label={actionLabel(t, name)}
      hint={name}
      checked={draft.event_types.includes(name)}
      onChange={(e) =>
        patch({
          event_types: e.target.checked
            ? [...draft.event_types, name]
            : draft.event_types.filter((x) => x !== name),
        })
      }
    />
  );
  return (
    <div className="admin-grid">
      <AdminSection
        icon="flame"
        title={t("gamification:admin.tabs.streak")}
        description={t("gamification:admin.streak.hint")}
        actions={
          <StatusBadge tone={draft.enabled ? "ok" : "neutral"}>
            {draft.enabled ? t("gamification:admin.on") : t("gamification:admin.off")}
          </StatusBadge>
        }
      >
        <CheckboxField
          label={t("gamification:admin.streak.enabled")}
          checked={draft.enabled}
          onChange={(e) => patch({ enabled: e.target.checked })}
        />
        <fieldset className="gam-fieldset">
          <legend>{t("gamification:admin.streak.tiers")}</legend>
          {tiers.map((tier, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: a tier's days are being edited, the row stays
            <div key={index} className="gam-tier">
              <TextField
                label={t("gamification:admin.streak.days")}
                type="number"
                min={2}
                max={366}
                value={String(tier.days)}
                onChange={(e) =>
                  patch({
                    tiers: tiers.map((x, i) => (i === index ? { ...x, days: Number(e.target.value) } : x)),
                  })
                }
              />
              <TextField
                label={t("gamification:admin.streak.multiplier")}
                type="number"
                min={1.05}
                max={10}
                step="0.05"
                value={String(tier.multiplier)}
                onChange={(e) =>
                  patch({
                    tiers: tiers.map((x, i) =>
                      i === index ? { ...x, multiplier: Number(e.target.value) } : x,
                    ),
                  })
                }
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("gamification:admin.remove")}
                onClick={() => patch({ tiers: tiers.filter((_, i) => i !== index) })}
              >
                <Icon name="trash" size={16} />
              </Button>
            </div>
          ))}
          <Button
            variant="secondary"
            onClick={() => {
              const last = ordered.at(-1);
              patch({
                tiers: [
                  ...tiers,
                  { days: (last?.days ?? 0) + (last ? 3 : 2), multiplier: (last?.multiplier ?? 1) + 0.5 },
                ],
              });
            }}
          >
            <Icon name="plus" size={16} />
            {t("gamification:admin.streak.addTier")}
          </Button>
        </fieldset>
        <fieldset className="gam-fieldset">
          <legend>{t("gamification:admin.streak.values")}</legend>
          <div className="gam-checks">
            {VALUES.map((value) => (
              <CheckboxField
                key={value}
                label={t(`gamification:value.${value}`)}
                checked={draft.values.includes(value)}
                onChange={(e) =>
                  patch({
                    values: e.target.checked
                      ? [...draft.values, value]
                      : draft.values.filter((v) => v !== value),
                  })
                }
              />
            ))}
          </div>
        </fieldset>
        {save.isError ? (
          <p role="alert" className="services-admin__ko">
            {t("gamification:admin.saveFailed")}
          </p>
        ) : null}
        {saved ? <p role="status">{t("gamification:admin.saved")}</p> : null}
        <FormActions>
          <Button
            disabled={save.isPending}
            onClick={() => save.mutate({ ...draft, tiers: ordered }, { onSuccess: () => setSaved(true) })}
          >
            <Icon name="check" size={16} />
            {t("gamification:admin.save")}
          </Button>
        </FormActions>
      </AdminSection>
      <AdminSection icon="chart" title={t("gamification:admin.streak.preview")}>
        <ol className="gam-streak" aria-label={t("gamification:admin.streak.preview")}>
          {Array.from({ length: horizon }, (_, i) => i + 1).map((day) => {
            const factor = multiplierAt(tiers, day);
            const tier = tiers.some((x) => x.days === day);
            return (
              <li key={day} data-tier={tier || undefined} data-boost={factor > 1 || undefined}>
                <span className="gam-streak__flame" aria-hidden="true">
                  <Icon name="flame" size={14 + Math.min(10, Math.round((factor - 1) * 6))} />
                </span>
                <span className="gam-streak__day">{t("gamification:admin.streak.day", { day })}</span>
                <strong>×{factor}</strong>
              </li>
            );
          })}
        </ol>
        <p className="admin-muted">
          {t("gamification:admin.streak.example", {
            base: 20,
            boosted: Math.floor(20 * multiplierAt(tiers, horizon)),
            days: horizon,
          })}
        </p>
      </AdminSection>
      <MemberStreaks />
      <AdminSection
        span="full"
        icon="play"
        title={t("gamification:admin.streak.counted")}
        description={t("gamification:admin.streak.countedHint")}
      >
        <div className="gam-checks gam-checks--wide">{counted.map(box)}</div>
        {others.length ? (
          <details className="gam-advanced">
            <summary>{t("gamification:admin.streak.otherActions", { count: others.length })}</summary>
            <div className="gam-checks gam-checks--wide">{others.map(box)}</div>
          </details>
        ) : null}
      </AdminSection>
    </div>
  );
}
