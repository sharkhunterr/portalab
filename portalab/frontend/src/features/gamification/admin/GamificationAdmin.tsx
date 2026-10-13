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
// issue 105: no « economy » tab — a member's balances are given and taken in the shop's console
const SIMPLE = ["overview", "progression", "levels", "streak", "achievements", "quests"];
const DETAILED = ["overview", "progression", "actions", "levels", "streak", "achievements", "quests"];

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
  const tabs = mode === "detailed" ? DETAILED : SIMPLE;
  const tab = tabs.includes(params.get("tab") ?? "") ? (params.get("tab") as string) : "overview";
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
            const keep = (next === "detailed" ? DETAILED : SIMPLE).includes(tab) ? tab : "overview";
            go({ mode: next, tab: keep });
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
          tabs={tabs.map((key) => ({ key, label: t(`gamification:admin.tabs.${key}`) }))}
        />
      }
    >
      {tab === "overview" ? <Overview /> : null}
      {tab === "progression" ? (
        <>
          <ProgressionTuner />
          {mode === "simple" ? (
            <p className="admin-muted">
              <Icon name="info" size={14} /> {t("gamification:admin.mode.simpleHint")}
            </p>
          ) : null}
        </>
      ) : null}
      {tab === "actions" ? <ActionRules /> : null}
      {tab === "levels" ? <LevelsPanel detailed={mode === "detailed"} /> : null}
      {tab === "streak" ? <StreakPanel /> : null}
      {tab === "achievements" ? <AchievementsPanel /> : null}
      {tab === "quests" ? <QuestsPanel /> : null}
    </AdminPage>
  );
}
