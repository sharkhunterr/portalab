import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { FormActions } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";

/**
 * 027: what an outage does, by service importance — an incident after a delay (closed when the service
 * is back), who is told and after how long (members, administrators, each by e-mail too), and whether the
 * trouble counts in the portal's health. The administrator sets one rule per importance here; each service
 * may override any field (``AlertingOverrides`` in its edit form).
 */
export const IMPORTANCES = ["critical", "major", "minor", "internal"] as const;
export type Importance = (typeof IMPORTANCES)[number];

export interface AlertRule {
  incident: boolean;
  incident_after: number;
  auto_resolve: boolean;
  notify_after: number;
  notify_members: boolean;
  notify_admins: boolean;
  email_members: boolean;
  email_admins: boolean;
  degrades_portal: boolean;
}
export type AlertOverrides = Partial<AlertRule>;
type Rules = Record<Importance, AlertRule>;

const RULES_KEY = ["admin", "services", "alert-rules"] as const;
const MAX_DELAY = 1440;

export function useAlertRules() {
  return useQuery({
    queryKey: RULES_KEY,
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/health/alert-rules")).data as unknown as { rules: Rules; defaults: Rules },
  });
}

/** The rule in words — one line under each importance (« incident after 10 min · members and admins »). */
export function useRuleSummary() {
  const t = useT();
  return (rule: AlertRule): string => {
    const parts = [
      rule.incident
        ? t("admin:alerting.summary.incident", { minutes: rule.incident_after })
        : t("admin:alerting.summary.noIncident"),
    ];
    const told = [
      rule.notify_members ? t("admin:alerting.summary.members") : null,
      rule.notify_admins ? t("admin:alerting.summary.admins") : null,
    ].filter(Boolean);
    parts.push(
      told.length
        ? t("admin:alerting.summary.told", { who: told.join(" + "), minutes: rule.notify_after })
        : t("admin:alerting.summary.nobody"),
    );
    if ((rule.notify_members && rule.email_members) || (rule.notify_admins && rule.email_admins)) {
      parts.push(t("admin:alerting.summary.email"));
    }
    return parts.join(" · ");
  };
}

function minutes(value: string): number {
  const n = Math.round(Number(value));
  return Number.isFinite(n) ? Math.max(0, Math.min(MAX_DELAY, n)) : 0;
}

/** The fields of one rule (the administrator's rule for an importance). */
function RuleFields({ rule, onChange }: { rule: AlertRule; onChange: (rule: AlertRule) => void }) {
  const t = useT();
  const set = (patch: AlertOverrides) => onChange({ ...rule, ...patch });
  return (
    <div className="alert-rule">
      <fieldset className="alert-rule__group">
        <legend>
          <Icon name="alert" size={16} /> {t("admin:alerting.incident")}
        </legend>
        <CheckboxField
          label={t("admin:alerting.incident.create")}
          checked={rule.incident}
          onChange={(e) => set({ incident: e.target.checked })}
        />
        <div className="alert-rule__row">
          <TextField
            label={t("admin:alerting.incident.after")}
            type="number"
            min={1}
            max={MAX_DELAY}
            disabled={!rule.incident}
            value={String(rule.incident_after)}
            onChange={(e) => set({ incident_after: Math.max(1, minutes(e.target.value)) })}
          />
          <CheckboxField
            label={t("admin:alerting.incident.autoResolve")}
            disabled={!rule.incident}
            checked={rule.auto_resolve}
            onChange={(e) => set({ auto_resolve: e.target.checked })}
          />
        </div>
      </fieldset>
      <fieldset className="alert-rule__group">
        <legend>
          <Icon name="bell" size={16} /> {t("admin:alerting.notify")}
        </legend>
        <TextField
          label={t("admin:alerting.notify.after")}
          hint={t("admin:alerting.notify.afterHint")}
          type="number"
          min={0}
          max={MAX_DELAY}
          value={String(rule.notify_after)}
          onChange={(e) => set({ notify_after: minutes(e.target.value) })}
        />
        <div className="alert-rule__audiences">
          <div className="alert-rule__audience">
            <CheckboxField
              label={t("admin:alerting.notify.members")}
              checked={rule.notify_members}
              onChange={(e) => set({ notify_members: e.target.checked })}
            />
            <CheckboxField
              label={t("admin:alerting.notify.email")}
              disabled={!rule.notify_members}
              checked={rule.email_members}
              onChange={(e) => set({ email_members: e.target.checked })}
            />
          </div>
          <div className="alert-rule__audience">
            <CheckboxField
              label={t("admin:alerting.notify.admins")}
              checked={rule.notify_admins}
              onChange={(e) => set({ notify_admins: e.target.checked })}
            />
            <CheckboxField
              label={t("admin:alerting.notify.email")}
              disabled={!rule.notify_admins}
              checked={rule.email_admins}
              onChange={(e) => set({ email_admins: e.target.checked })}
            />
          </div>
        </div>
      </fieldset>
      <fieldset className="alert-rule__group">
        <legend>
          <Icon name="heart" size={16} /> {t("admin:alerting.portal")}
        </legend>
        <CheckboxField
          label={t("admin:alerting.portal.degrades")}
          hint={t("admin:alerting.portal.degradesHint")}
          checked={rule.degrades_portal}
          onChange={(e) => set({ degrades_portal: e.target.checked })}
        />
      </fieldset>
    </div>
  );
}

/** The rules dialog at the top of the services administration: one tab per importance. */
export function AlertRulesDialog() {
  const t = useT();
  const queryClient = useQueryClient();
  const query = useAlertRules();
  const summary = useRuleSummary();
  const [open, setOpen] = useState(false);
  const [level, setLevel] = useState<Importance>("critical");
  const [draft, setDraft] = useState<Rules | null>(null);
  const save = useMutation({
    mutationFn: async (rules: Rules) => (await api.PUT("/api/v1/health/alert-rules", { body: rules })).data,
    onSuccess: () => {
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: RULES_KEY });
      void queryClient.invalidateQueries({ queryKey: ["admin", "services"] });
    },
  });
  const rules = draft ?? query.data?.rules ?? null;
  const defaults = query.data?.defaults;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setDraft(query.data?.rules ?? null);
          save.reset();
        }
      }}
      size="lg"
      title={t("admin:alerting.title")}
      description={t("admin:alerting.description")}
      closeLabel={t("admin:services.close")}
      trigger={
        <Button type="button" variant="secondary" disabled={!query.data}>
          <Icon name="shield" size={18} />
          {t("admin:alerting.open")}
        </Button>
      }
    >
      {rules ? (
        <form
          className="services-admin__form"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(rules);
          }}
        >
          <div className="alert-levels" role="tablist" aria-label={t("admin:services.importance")}>
            {IMPORTANCES.map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={level === key}
                className="alert-levels__tab"
                data-importance={key}
                onClick={() => setLevel(key)}
              >
                <strong>{t(`admin:services.importance.${key}`)}</strong>
                <span>{summary(rules[key])}</span>
              </button>
            ))}
          </div>
          <div role="tabpanel" aria-label={t(`admin:services.importance.${level}`)}>
            <RuleFields rule={rules[level]} onChange={(rule) => setDraft({ ...rules, [level]: rule })} />
          </div>
          {save.isError ? (
            <p role="alert" className="services-admin__ko">
              {save.error instanceof ApiError ? save.error.message : t("admin:services.refused")}
            </p>
          ) : null}
          <FormActions>
            {defaults ? (
              <Button
                type="button"
                variant="ghost"
                onClick={() => setDraft({ ...rules, [level]: defaults[level] })}
              >
                <Icon name="sync" size={16} />
                {t("admin:alerting.reset")}
              </Button>
            ) : null}
            <Button type="submit" disabled={save.isPending}>
              <Icon name="check" size={16} />
              {t("admin:alerting.save")}
            </Button>
          </FormActions>
        </form>
      ) : null}
    </Dialog>
  );
}

const FLAGS = [
  "incident",
  "auto_resolve",
  "notify_members",
  "email_members",
  "notify_admins",
  "email_admins",
  "degrades_portal",
] as const;
const DELAYS = ["incident_after", "notify_after"] as const;

/**
 * A service's own alerting: each field follows its importance's rule (shown) unless set here — a yes/no
 * choice for the switches, a number of minutes for the delays (empty: the rule's).
 */
export function AlertingOverrides({
  importance,
  value,
  onChange,
}: {
  importance: Importance;
  value: AlertOverrides;
  onChange: (value: AlertOverrides) => void;
}) {
  const t = useT();
  const query = useAlertRules();
  const rule = query.data?.rules[importance];
  const yesNo = (on: boolean | undefined) => (on ? t("admin:alerting.yes") : t("admin:alerting.no"));
  const setFlag = (key: (typeof FLAGS)[number], choice: string) => {
    const next = { ...value };
    if (choice === "") delete next[key];
    else next[key] = choice === "yes";
    onChange(next);
  };
  const setDelay = (key: (typeof DELAYS)[number], text: string) => {
    const next = { ...value };
    if (!text.trim()) delete next[key];
    else next[key] = key === "incident_after" ? Math.max(1, minutes(text)) : minutes(text);
    onChange(next);
  };
  const overridden = Object.keys(value).length;
  return (
    <div className="alert-overrides">
      <p className="admin-muted">
        {rule
          ? t("admin:alerting.overrides.follows", {
              importance: t(`admin:services.importance.${importance}`),
            })
          : null}
        {overridden ? (
          <Button type="button" variant="ghost" onClick={() => onChange({})}>
            <Icon name="sync" size={14} />
            {t("admin:alerting.overrides.clear", { count: overridden })}
          </Button>
        ) : null}
      </p>
      <div className="alert-overrides__grid">
        {DELAYS.map((key) => (
          <TextField
            key={key}
            label={t(`admin:alerting.field.${key}`)}
            hint={rule ? t("admin:alerting.overrides.minutes", { minutes: rule[key] }) : undefined}
            type="number"
            min={key === "incident_after" ? 1 : 0}
            max={MAX_DELAY}
            placeholder={rule ? String(rule[key]) : ""}
            value={value[key] === undefined ? "" : String(value[key])}
            onChange={(e) => setDelay(key, e.target.value)}
            data-overridden={value[key] !== undefined || undefined}
          />
        ))}
        {FLAGS.map((key) => (
          <SelectField
            key={key}
            label={t(`admin:alerting.field.${key}`)}
            value={value[key] === undefined ? "" : value[key] ? "yes" : "no"}
            onChange={(e) => setFlag(key, e.target.value)}
            data-overridden={value[key] !== undefined || undefined}
          >
            <option value="">{t("admin:alerting.overrides.rule", { value: yesNo(rule?.[key]) })}</option>
            <option value="yes">{t("admin:alerting.yes")}</option>
            <option value="no">{t("admin:alerting.no")}</option>
          </SelectField>
        ))}
      </div>
    </div>
  );
}
