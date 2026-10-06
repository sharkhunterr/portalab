import { Progress } from "../../../design-system/components/Content";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import "../gamification.css";

/** A quest, daily objective or challenge as both the 013 and 012 APIs describe it. */
export interface QuestItem {
  key: string;
  kind: "quest" | "daily" | "challenge" | string;
  label: string;
  description?: string | null;
  period?: string | null;
  ends_at?: string | null;
  completed: boolean;
  steps: Array<{ current: number; target: number }>;
  rewards: Array<{ value: string; amount: number }>;
}

/**
 * Quest list (spec 013 T039): kind and state in **text** (never color alone), step progress, rewards, and
 * the end of a time-boxed challenge.
 */
export function QuestList({ quests }: { quests: QuestItem[] }) {
  const t = useT();
  const format = useFormat();
  if (quests.length === 0) return <p>{t("gamification:quests.empty")}</p>;
  return (
    <ul className="gamification-grid">
      {quests.map((quest) => (
        <li key={quest.key} className="ds-card ds-stack" data-state={quest.completed ? "completed" : "open"}>
          <h3>{quest.label}</h3>
          <p className="ds-badge">
            {t(
              `gamification:quests.kind.${
                quest.kind === "daily" && quest.period && quest.period !== "day"
                  ? `daily_${quest.period}`
                  : quest.kind
              }`,
            )}{" "}
            · {t(quest.completed ? "gamification:quests.completed" : "gamification:quests.open")}
          </p>
          {quest.description ? <p>{quest.description}</p> : null}
          {quest.steps.map((step, index) => (
            <Progress
              // biome-ignore lint/suspicious/noArrayIndexKey: steps are positional
              key={index}
              value={step.current}
              max={step.target}
              label={t("gamification:achievements.progress", step)}
            />
          ))}
          {quest.rewards.length ? (
            <p className="gamification-meta">
              {quest.rewards
                .map((reward) =>
                  t("gamification:quests.reward", {
                    amount: reward.amount,
                    value: t(`gamification:value.${reward.value}`),
                  }),
                )
                .join(" · ")}
            </p>
          ) : null}
          {quest.ends_at ? (
            <p className="gamification-meta">
              {t("gamification:quests.endsAt", { date: format.dateTime(quest.ends_at) })}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
