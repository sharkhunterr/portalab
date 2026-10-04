import { useT } from "../../../i18n/hooks/useT";
import { AnomalyQueue } from "./AnomalyQueue";
import { LevelCurve } from "./LevelCurve";
import { ManualGrant } from "./ManualGrant";
import { RuleEditor } from "./RuleEditor";
import "../gamification.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/** ``/admin/gamification`` (spec 013): rules, manual rewards, anomaly review, level curve and verification. */
export default function GamificationAdmin() {
  const t = useT();
  return (
    <div className="ds-stack">
      <PageHeader icon="trophy" title={t("gamification:admin.title")} />
      <RuleEditor />
      <ManualGrant />
      <AnomalyQueue />
      <LevelCurve />
    </div>
  );
}
