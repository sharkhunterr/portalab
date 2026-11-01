import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Project } from "../api";
import { LIFECYCLE, STATE_ICON } from "./parts";

/**
 * Lifecycle timeline (spec 015 T014; issue 304: horizontal): every step in a row — its icon **and** its
 * name, the date it was reached — the current one lit, those to come faded; a project refused or abandoned
 * ends on that step, stated. Swiped sideways on a phone.
 */
export function Timeline({ project }: { project: Project }) {
  const t = useT();
  const format = useFormat();
  const reached = new Map((project.history ?? []).map((h) => [h.to_state, h.at]));
  const failed = project.state === "rejected" || project.state === "abandoned";
  const steps: string[] = [...LIFECYCLE.filter((state) => !failed || reached.has(state))];
  if (failed) steps.push(project.state);
  return (
    <section aria-labelledby="project-timeline" className="project-journey">
      <h2 id="project-timeline">
        <Icon name="flag" size={18} /> {t("marketplace:project.timeline")}
      </h2>
      <ol className="project-journey__steps">
        {steps.map((state) => {
          const at = reached.get(state);
          const current = project.state === state;
          return (
            <li
              key={state}
              aria-current={current ? "step" : undefined}
              data-step={current ? "current" : at ? "done" : "todo"}
              data-failed={(failed && current) || undefined}
            >
              <span className="project-journey__dot">
                <Icon name={at && !current ? "check" : (STATE_ICON[state] ?? "lightbulb")} size={16} />
              </span>
              <span className="project-journey__name">{t(`marketplace:state.${state}`)}</span>
              <span className="project-journey__date">{at ? format.date(at) : "—"}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
