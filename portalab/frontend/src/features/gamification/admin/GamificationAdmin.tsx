import { AdminGrid, AdminPage } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import { AnomalyQueue } from "./AnomalyQueue";
import { LevelCurve } from "./LevelCurve";
import { ManualGrant } from "./ManualGrant";
import { RuleEditor } from "./RuleEditor";
import "../gamification.css";

/** ``/admin/gamification`` (spec 013, 027 administration kit): rules, manual rewards, anomaly review, level curve. */
export default function GamificationAdmin() {
  const t = useT();
  return (
    <AdminPage
      icon="trophy"
      title={t("gamification:admin.title")}
      description={t("gamification:admin.description")}
    >
      <RuleEditor />
      <AdminGrid>
        <ManualGrant />
        <AnomalyQueue />
      </AdminGrid>
      <LevelCurve />
    </AdminPage>
  );
}
