import { useState } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useAnomalies, useAnomalyDecision } from "../api";

/** Anomaly review (spec 013 T022, ``economy.manage``): withheld rewards wait for an audited decision. */
export function AnomalyQueue() {
  const t = useT();
  const format = useFormat();
  const anomalies = useAnomalies();
  const decide = useAnomalyDecision();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  return (
    <AdminSection title={t("gamification:admin.anomalies")} icon="alert">
      {anomalies.data?.length === 0 ? <p>{t("gamification:admin.anomalies.empty")}</p> : null}
      <ul className="ds-stack">
        {(anomalies.data ?? []).map((flag) => {
          const reason = reasons[flag.id] ?? "";
          return (
            <li key={flag.id} className="ds-card">
              <h3>{t(`gamification:admin.anomaly.kind.${flag.kind}`)}</h3>
              <p className="gamification-meta">
                {flag.user_id} · {format.dateTime(flag.window_start)} ·{" "}
                {t("gamification:admin.anomaly.withheld", { count: flag.withheld.length })}
              </p>
              <TextField
                label={t("gamification:admin.anomaly.reason")}
                value={reason}
                onChange={(e) => setReasons({ ...reasons, [flag.id]: e.target.value })}
              />
              <div className="ds-stack--row">
                {(["approve", "reject", "confirm-abuse"] as const).map((decision) => (
                  <Button
                    key={decision}
                    variant={decision === "approve" ? "primary" : "secondary"}
                    disabled={reason.trim().length < 3 || decide.isPending}
                    onClick={() => decide.mutate({ id: flag.id, decision, reason })}
                  >
                    {t(`gamification:admin.anomaly.${decision === "confirm-abuse" ? "confirm" : decision}`)}
                  </Button>
                ))}
              </div>
            </li>
          );
        })}
      </ul>
    </AdminSection>
  );
}
