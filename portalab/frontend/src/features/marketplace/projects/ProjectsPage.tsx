import { Link } from "react-router";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useProjects } from "../api";
import { MyFundings } from "./MyFundings";
import "../marketplace.css";

/** ``/projects`` (spec 015 slice A): community projects with their state and public totals; my fundings. */
export default function ProjectsPage() {
  const t = useT();
  const format = useFormat();
  const projects = useProjects();
  return (
    <div className="ds-stack">
      <h1>{t("marketplace:projects.title")}</h1>
      {projects.isError ? <FunctionalState state="unavailable" onRetry={() => projects.refetch()} /> : null}
      {projects.data?.length === 0 ? (
        <p>
          {t("marketplace:projects.empty")}{" "}
          <Link to="/community/proposals">{t("marketplace:projects.propose")}</Link>
        </p>
      ) : null}
      <ul className="project-grid">
        {(projects.data ?? []).map((project) => (
          <li key={project.id} className="ds-card ds-stack">
            <h2>
              <Link to={`/projects/${project.id}`}>{project.title}</Link>
            </h2>
            <p className="ds-badge">{t(`marketplace:state.${project.state}`)}</p>
            <p>
              {t("marketplace:funding.totals", {
                reserved: format.number(project.totals.reserved),
                consumed: format.number(project.totals.consumed),
                funders: project.totals.funders,
              })}
            </p>
          </li>
        ))}
      </ul>
      <MyFundings />
    </div>
  );
}
