import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useApprovals, useAutomationAdmin } from "../api";

/** Approvals inbox (spec 019 T030, ``automation.approve``): action-generated summary, approve or reject. */
export function Inbox() {
  const t = useT();
  const format = useFormat();
  const approvals = useApprovals();
  const { decide } = useAutomationAdmin();
  return (
    <AdminSection title={t("automations:approvals.title")} icon="check">
      {approvals.data?.length === 0 ? <p>{t("automations:approvals.empty")}</p> : null}
      <ul className="ds-stack">
        {(approvals.data ?? []).map((approval) => (
          <li key={approval.id} className="ds-card ds-stack">
            <p>
              <strong>{approval.action}</strong> — {approval.summary}
            </p>
            <p className="automation-meta">
              {t("automations:approvals.expires", { date: format.dateTime(approval.expires_at) })}
            </p>
            <div className="ds-stack--row">
              <Button onClick={() => decide.mutate({ id: approval.id, decision: "approve" })}>
                {t("automations:approvals.approve")}
              </Button>
              <Button
                variant="secondary"
                onClick={() => decide.mutate({ id: approval.id, decision: "reject" })}
              >
                {t("automations:approvals.reject")}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}
