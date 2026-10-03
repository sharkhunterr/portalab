import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Project } from "../api";

const PATH = ["idea", "proposal", "open", "validation", "development", "beta", "released"] as const;

/** Lifecycle timeline (spec 015 T014): every step with icon **and** text; off-ramps stated explicitly. */
export function Timeline({ project }: { project: Project }) {
  const t = useT();
  const format = useFormat();
  const reached = new Map((project.history ?? []).map((h) => [h.to_state, h.at]));
  const failed = project.state === "rejected" || project.state === "abandoned";
  return (
    <section aria-labelledby="project-timeline" className="ds-stack">
      <h2 id="project-timeline">{t("marketplace:project.timeline")}</h2>
      <ol className="project-timeline">
        {PATH.map((state) => {
          const at = reached.get(state);
          const current = project.state === state;
          return (
            <li key={state} aria-current={current ? "step" : undefined} data-done={at ? "true" : "false"}>
              <FunctionalState
                state={at ? (current ? "available" : "no-data") : "unavailable"}
                label={`${t(`marketplace:state.${state}`)}${at ? ` · ${format.date(at)}` : ""}`}
              />
            </li>
          );
        })}
      </ol>
      {failed ? <FunctionalState state="error" label={t(`marketplace:state.${project.state}`)} /> : null}
      {(project.notes ?? []).length ? (
        <ul className="ds-stack">
          {(project.notes ?? []).map((note) => (
            <li key={`${note.state}-${note.at}`} className="ds-card">
              <strong>{t(`marketplace:state.${note.state}`)}</strong> — {note.note}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
