import { AdminPage } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import { AnomalyQueue } from "./AnomalyQueue";
import "../gamification.css";

/**
 * ``/admin/gamification/abuse`` (admin reorganisation, trial): the rewards withheld as suspicious, waiting
 * for a decision — a page of the Engagement hub rather than the bottom of its overview.
 */
export default function AbuseAdmin() {
  const t = useT();
  return (
    <AdminPage
      icon="shield"
      title={t("gamification:admin.abuse.title")}
      description={t("gamification:admin.abuse.subtitle")}
    >
      <AnomalyQueue />
    </AdminPage>
  );
}
