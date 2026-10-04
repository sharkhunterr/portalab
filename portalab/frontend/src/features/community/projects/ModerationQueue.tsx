import { useState } from "react";
import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { SafeHtml } from "../../content/SafeHtml";
import { useModeration } from "./api";

/** ``/admin/community/moderation`` (spec 012 T023, ``community.moderate``): approve or reject proposals. */
export default function ModerationQueue() {
  const t = useT();
  const { queue, decide } = useModeration();
  const [reason, setReason] = useState("");
  return (
    <AdminPage
      icon="users"
      title={t("community:moderation.title")}
      description={t("community:moderation.description")}
    >
      <AdminSection title={t("community:moderation.queue")} icon="inbox">
        <TextField
          label={t("community:moderation.reason")}
          value={reason}
          maxLength={500}
          onChange={(e) => setReason(e.target.value)}
        />
        {queue.isError ? <FunctionalState state="unavailable" onRetry={() => queue.refetch()} /> : null}
        {queue.data?.length === 0 ? <p className="admin-muted">{t("community:moderation.empty")}</p> : null}
        <ul className="ds-stack">
          {(queue.data ?? []).map((proposal) => (
            <li key={proposal.id} className="ds-card ds-stack">
              <h2>{proposal.title}</h2>
              <SafeHtml html={proposal.rendered_html} diagrams={false} />
              <div className="ds-stack--row">
                <Button onClick={() => decide.mutate({ id: proposal.id, approve: true, reason })}>
                  {t("community:moderation.approve")}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => decide.mutate({ id: proposal.id, approve: false, reason })}
                >
                  {t("community:moderation.reject")}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}
