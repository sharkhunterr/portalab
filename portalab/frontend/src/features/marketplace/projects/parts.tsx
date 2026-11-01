import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Project } from "../api";

/** A project's way, idea → released, and its stages as members filter them (issue 303: shared with the
 * administrators' console). */
export const LIFECYCLE = [
  "idea",
  "proposal",
  "open",
  "validation",
  "development",
  "beta",
  "released",
] as const;
export const STAGES: Record<string, readonly string[]> = {
  funding: ["open"],
  proposed: ["idea", "proposal", "validation"],
  building: ["development", "beta"],
  released: ["released"],
  closed: ["rejected", "abandoned"],
};
export const STATE_ICON: Record<string, string> = {
  idea: "lightbulb",
  proposal: "message",
  open: "coins",
  validation: "check",
  development: "wrench",
  beta: "bolt",
  released: "rocket",
  rejected: "blocked",
  abandoned: "close",
};

/** Where the project is on its way: the steps as a bar, and in words (« Step 2 of 7 »). */
export function Stepper({ state }: { state: string }) {
  const t = useT();
  const index = LIFECYCLE.indexOf(state as (typeof LIFECYCLE)[number]);
  return (
    <div className="project-progress">
      <ol className="project-steps" aria-hidden="true">
        {LIFECYCLE.map((step, i) => (
          <li
            key={step}
            data-done={index >= 0 && i < index ? "true" : undefined}
            data-current={i === index ? "true" : undefined}
            title={t(`marketplace:state.${step}`)}
          />
        ))}
      </ol>
      {index >= 0 ? (
        <span className="project-progress__label">
          {t("marketplace:projects.step", { step: index + 1, total: LIFECYCLE.length })}
        </span>
      ) : null}
    </div>
  );
}

/** What the project gathered, toward its goal when it has one. */
export function Gathered({ project }: { project: Project }) {
  const t = useT();
  const format = useFormat();
  const gathered = project.totals.reserved + project.totals.consumed;
  const goal = project.totals.goal_amount;
  return goal ? (
    <div className="project-goal">
      <progress value={Math.min(gathered, goal)} max={goal} />
      <span>
        {t("marketplace:projects.goal", { gathered: format.number(gathered), goal: format.number(goal) })}
      </span>
    </div>
  ) : null;
}
