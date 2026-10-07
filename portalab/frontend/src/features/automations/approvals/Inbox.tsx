import { AdminEmpty } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useApprovals, useAutomationAdmin, useCatalog } from "../api";
import { ACTION_ICONS, actionLabel } from "../labels";

/** Approvals inbox (spec 019 T030, ``automation.approve``; 027 redesign): what waits, until when, decide. */
export function Inbox() {
  const t = useT();
  const format = useFormat();
  const approvals = useApprovals();
  const catalog = useCatalog().data;
  const { decide } = useAutomationAdmin();
  if (approvals.data?.length === 0)
    return <AdminEmpty icon="check" title={t("automations:approvals.empty")} />;
  return (
    <ul className="automation-approvals">
      {(approvals.data ?? []).map((approval) => (
        <li key={approval.id} className="automation-approval ds-card">
          <span className="automation-card__icon" aria-hidden="true">
            <Icon name={ACTION_ICONS[approval.action] ?? "play"} size={20} />
          </span>
          <div className="automation-approval__main">
            <strong>{actionLabel(t, approval.action, catalog)}</strong>
            <p>{approval.summary}</p>
            <p className="automation-meta">
              {t("automations:approvals.expires", { date: format.dateTime(approval.expires_at) })}
            </p>
          </div>
          <div className="automation-approval__actions">
            <Button onClick={() => decide.mutate({ id: approval.id, decision: "approve" })}>
              <Icon name="check" size={16} />
              {t("automations:approvals.approve")}
            </Button>
            <Button
              variant="secondary"
              onClick={() => decide.mutate({ id: approval.id, decision: "reject" })}
            >
              <Icon name="close" size={16} />
              {t("automations:approvals.reject")}
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
