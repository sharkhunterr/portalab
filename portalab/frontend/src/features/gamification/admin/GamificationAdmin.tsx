import { useSearchParams } from "react-router";
import { AdminPage, AdminTabs } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { AchievementsPanel, QuestsPanel } from "./AchievementsPanel";
import { ActionRules } from "./ActionRules";
import { LevelsPanel } from "./LevelsPanel";
import { Overview } from "./Overview";
import { ProgressionTuner } from "./ProgressionTuner";
import { StreakPanel } from "./StreakPanel";
import "../gamification.css";

const MODE_KEY = "portalab.gamification.mode";
// issue 105: no « economy » tab — a member's balances are given and taken on their card. Admin
// reorganisation (trial): « gains » groups what earns (pace, XP per action, streaks), « achievements » the
// goals (achievements and quests); the former tabs still lead to their group.
const TABS = ["overview", "gains", "levels", "achievements"];
const FORMER: Record<string, string> = {
  progression: "gains",
  actions: "gains",
  streak: "gains",
  quests: "achievements",
};

function storedMode(): "simple" | "detailed" {
  try {
    return localStorage.getItem(MODE_KEY) === "detailed" ? "detailed" : "simple";
  } catch {
    return "simple";
  }
}

/**
 * ``/admin/gamification`` (spec 013; 027 redesign): two ways to tune the economy — **simple** (shape the
 * progression curve: one pace for every gain, level rewards, streaks) or **detailed** (also the XP of each
 * action and the level formula) — plus the overview (curves, anomalies), achievements and quests.
 */
export default function GamificationAdmin() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const mode =
    params.get("mode") === "detailed" || (!params.get("mode") && storedMode() === "detailed")
      ? "detailed"
      : "simple";
  const asked = params.get("tab") ?? "";
  const tab = TABS.includes(asked) ? asked : (FORMER[asked] ?? "overview");
  const go = (next: { tab?: string; mode?: string }) => {
    const nextMode = next.mode ?? mode;
    const nextTab = next.tab ?? tab;
    const out: Record<string, string> = {};
    if (nextTab !== "overview") out.tab = nextTab;
    if (nextMode === "detailed") out.mode = "detailed";
    setParams(out, { replace: true });
  };
  return (
    <AdminPage
      icon="trophy"
      title={t("gamification:admin.title")}
      description={t("gamification:admin.description")}
      wide
      secondary={
        <AdminTabs
          label={t("gamification:admin.mode.label")}
          current={mode}
          onChange={(next) => {
            try {
              localStorage.setItem(MODE_KEY, next);
            } catch {
              // a convenience only
            }
            go({ mode: next });
          }}
          tabs={[
            { key: "simple", label: t("gamification:admin.mode.simple") },
            { key: "detailed", label: t("gamification:admin.mode.detailed") },
          ]}
        />
      }
      tabs={
        <AdminTabs
          label={t("gamification:admin.title")}
          current={tab}
          onChange={(next) => go({ tab: next })}
          tabs={TABS.map((key) => ({ key, label: t(`gamification:admin.tabs.${key}`) }))}
        />
      }
    >
      {tab === "overview" ? <Overview /> : null}
      {tab === "gains" ? (
        <>
          <ProgressionTuner />
          {mode === "simple" ? (
            <p className="admin-muted">
              <Icon name="info" size={14} /> {t("gamification:admin.mode.simpleHint")}
            </p>
          ) : (
            <ActionRules />
          )}
          <StreakPanel />
        </>
      ) : null}
      {tab === "levels" ? <LevelsPanel detailed={mode === "detailed"} /> : null}
      {tab === "achievements" ? (
        <>
          <AchievementsPanel />
          <QuestsPanel />
        </>
      ) : null}
    </AdminPage>
  );
}
