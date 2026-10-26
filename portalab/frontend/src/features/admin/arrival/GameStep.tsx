import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { api } from "../../../api/client";
import { AdminTabs } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { CampaignList, CreateCampaign } from "../../campaigns/console/CampaignConsole";
import { AchievementsPanel, QuestsPanel } from "../../gamification/admin/AchievementsPanel";
import { ActionRules } from "../../gamification/admin/ActionRules";
import { LevelsPanel } from "../../gamification/admin/LevelsPanel";
import { ProgressionTuner } from "../../gamification/admin/ProgressionTuner";
import { StreakPanel } from "../../gamification/admin/StreakPanel";
import "./arrival.css";

/**
 * Issue 253 — the arrival wizard's game: the recommended install, the LAN's game as Portalab ships it (what
 * earns XP and Coins, the level curve and what each level unlocks, the achievements, the quests, the campaigns)
 * with its shop (Portalab's catalog, the LAN's own products), the same to adjust, or everything set by hand —
 * then the game administration's own screens, tab by tab. The recommended install is only chosen here: it is
 * put in place when the portal opens (``Open``), part after part, its visual packs with it; adjusted, it is
 * put in place here, part after part, for its screens to show it. The choice is kept with the wizard's
 * progress; applying the LAN's game twice changes nothing.
 */
export type GameChoice = "lan" | "tune" | "custom";

const CHOICES: ReadonlyArray<{ key: GameChoice; icon: string }> = [
  { key: "lan", icon: "sparkles" },
  { key: "tune", icon: "sliders" },
  { key: "custom", icon: "wrench" },
];
const TABS = ["levels", "gains", "achievements", "quests", "campaigns", "settings"] as const;
type Tab = (typeof TABS)[number];
// the recommended install, a request per task — the shop first: a level's reward names its products
export const GAME_TASKS = ["shop", "play", "achievements", "campaigns"] as const;
export type GameTask = (typeof GAME_TASKS)[number];
const TASK_PARTS: Record<GameTask, readonly string[]> = {
  shop: ["shop"],
  play: ["settings", "curve", "rules"],
  achievements: ["achievements", "quests"],
  campaigns: ["campaigns"],
}; // the packs: a task of their own at the opening, a few at a time
const NOT_SOLD = "product not in this shop";
const GAME_KEYS = [["admin", "gamification"], ["gamification"], ["campaigns"], ["admin", "config"]] as const;

interface Counts {
  catalog: number;
  packs: number;
  products: number;
  settings: number;
  rules: number;
  achievements: number;
  quests: number;
  campaigns: number;
  level_rewards: number;
}
interface Report {
  applied: Record<string, number>;
  kept: Record<string, number>;
  skipped: Array<{ part: string; key: string; reason: string }>;
}

export async function applyGame(task: GameTask): Promise<Report> {
  const { data, error } = await api.POST("/api/v1/admin/game/setup", {
    body: { preset: "lan", parts: TASK_PARTS[task] } as never,
  });
  if (error) throw error;
  return data as unknown as Report;
}

/** What the recommended install could not put in place (a product the shop does not sell is only said). */
export function notApplied(report: Report): string[] {
  return report.skipped.filter((s) => s.reason !== NOT_SOLD).map((s) => `${s.part} ${s.key}`);
}

function merged(reports: readonly Report[]): Report {
  const applied: Record<string, number> = {};
  for (const report of reports)
    for (const [part, count] of Object.entries(report.applied)) applied[part] = (applied[part] ?? 0) + count;
  return { applied, kept: {}, skipped: reports.flatMap((r) => r.skipped) };
}

export function GameStep({
  choice,
  onChoose,
  settings,
}: {
  choice: GameChoice | undefined;
  onChoose: (choice: GameChoice | undefined) => void;
  settings: ReactNode; // the play settings (time zone, contribution)
}) {
  const t = useT();
  const client = useQueryClient();
  const [tab, setTab] = useState<Tab>("levels");
  const [at, setAt] = useState(0); // the task being put in place (adjusted install)
  const presets = useQuery({
    queryKey: ["admin", "game", "presets"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/game/presets")).data as unknown as Array<{
        key: string;
        counts: Counts;
      }>,
  });
  const lan = (Array.isArray(presets.data) ? presets.data : []).find((p) => p.key === "lan")?.counts;
  const apply = useMutation({
    mutationFn: async () => {
      const reports: Report[] = [];
      for (const [index, task] of GAME_TASKS.entries()) {
        setAt(index);
        reports.push(await applyGame(task));
      }
      return merged(reports);
    },
    onSuccess: async () => {
      await Promise.all(GAME_KEYS.map((queryKey) => client.invalidateQueries({ queryKey })));
    },
  });
  const choose = (next: GameChoice) => {
    if (next !== "tune") {
      onChoose(next); // the recommended install: put in place when the portal opens
      return;
    }
    apply.mutate(undefined, { onSuccess: () => onChoose(next) });
  };

  if (!choice) {
    return (
      <>
        <div className="arrival__choices arrival__choices--three">
          {CHOICES.map(({ key, icon }) => (
            <button
              key={key}
              type="button"
              className="arrival__choice"
              disabled={apply.isPending}
              onClick={() => choose(key)}
            >
              <span className="arrival__choice-icon" aria-hidden="true">
                <Icon name={icon} size={22} />
              </span>
              <strong>{t(`account:arrival.game.${key}`)}</strong>
              <span>
                {t(`account:arrival.game.${key}Hint`)}
                {key !== "custom" && lan ? ` ${t("account:arrival.game.contains", { ...lan })}` : ""}
              </span>
            </button>
          ))}
        </div>
        {apply.isPending ? (
          <p className="arrival__note" role="status">
            <span className="launch__spinner" aria-hidden="true" />
            {t("account:arrival.game.applying", {
              part: t(`account:arrival.open.task.${GAME_TASKS[at]}`),
              step: at + 1,
              total: GAME_TASKS.length,
            })}
          </p>
        ) : null}
        {apply.isError ? <p role="alert">{t("account:arrival.error")}</p> : null}
        {settings}
      </>
    );
  }

  const report = apply.data;
  const missing = report?.skipped.filter((s) => s.reason === NOT_SOLD) ?? [];
  const failed = report ? notApplied(report) : [];
  return (
    <>
      <p className="arrival__note" role="status">
        <Icon name={choice === "custom" ? "wrench" : "check"} size={16} />
        <span>
          {t(`account:arrival.game.chosen.${choice}`)}
          {report ? ` ${t("account:arrival.game.done", { ...report.applied })}` : ""}
        </span>
        <Button variant="ghost" onClick={() => onChoose(undefined)}>
          {t("account:arrival.game.change")}
        </Button>
      </p>
      {missing.length ? (
        <p className="arrival__note">
          <Icon name="info" size={16} />
          {t("account:arrival.game.missing", {
            count: missing.length,
            products: missing.map((m) => m.key.split(": ").pop()).join(", "),
          })}
        </p>
      ) : null}
      {failed.length ? (
        <p role="alert">{t("account:arrival.game.failed", { keys: failed.join(", ") })}</p>
      ) : null}
      {choice === "lan" ? (
        settings
      ) : (
        <>
          <AdminTabs
            label={t("account:arrival.game.tabs")}
            current={tab}
            onChange={(next) => setTab(next as Tab)}
            tabs={TABS.map((key) => ({ key, label: t(`account:arrival.game.tab.${key}`) }))}
          />
          <div className="arrival__game">
            {tab === "levels" ? <LevelsPanel detailed /> : null}
            {tab === "gains" ? (
              <>
                <ProgressionTuner />
                <ActionRules />
                <StreakPanel />
              </>
            ) : null}
            {tab === "achievements" ? <AchievementsPanel /> : null}
            {tab === "quests" ? <QuestsPanel /> : null}
            {tab === "campaigns" ? (
              <>
                <p>
                  <CreateCampaign />
                </p>
                <CampaignList />
              </>
            ) : null}
            {tab === "settings" ? settings : null}
          </div>
        </>
      )}
    </>
  );
}
