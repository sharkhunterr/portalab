import { useT } from "../../../i18n/hooks/useT";
import { AnomalyQueue } from "./AnomalyQueue";
import { LevelCurve } from "./LevelCurve";
import { ManualGrant } from "./ManualGrant";
import { RuleEditor } from "./RuleEditor";
import "../gamification.css";

/** ``/admin/gamification`` (spec 013): rules, manual rewards, anomaly review, level curve and verification. */
export default function GamificationAdmin() {
  const t = useT();
  return (
    <div className="ds-stack">
      <h1>{t("gamification:admin.title")}</h1>
      <RuleEditor />
      <ManualGrant />
      <AnomalyQueue />
      <LevelCurve />
    </div>
  );
}
