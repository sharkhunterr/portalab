import { useMemo, useState } from "react";
import { Link } from "react-router";
import { AdminEmpty, AdminStats } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Project, useMyFundings, useProjects } from "../api";
import { MyFundings } from "./MyFundings";
import "../marketplace.css";

/**
 * ``/projects`` (spec 015 slice A; 027 redesign): community projects as cards — where each one is on its
 * way (idea → released), what it gathered and from how many members — filtered by stage, with the key
 * figures, a way to launch one (a shop purchase) and my fundings.
 */
const LIFECYCLE = ["idea", "proposal", "open", "validation", "development", "beta", "released"] as const;
const STAGES: Record<string, readonly string[]> = {
  funding: ["open"],
  proposed: ["idea", "proposal", "validation"],
  building: ["development", "beta"],
  released: ["released"],
  closed: ["rejected", "abandoned"],
};
const STATE_ICON: Record<string, string> = {
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

function Stepper({ state }: { state: string }) {
  const t = useT();
  const index = LIFECYCLE.indexOf(state as (typeof LIFECYCLE)[number]);
  return (
    <ol className="project-steps" aria-label={t(`marketplace:state.${state}`)}>
      {LIFECYCLE.map((step, i) => (
        <li
          key={step}
          data-done={index >= 0 && i < index ? "true" : undefined}
          data-current={i === index ? "true" : undefined}
          title={t(`marketplace:state.${step}`)}
        />
      ))}
    </ol>
  );
}

function ProjectCard({ project }: { project: Project }) {
  const t = useT();
  const format = useFormat();
  return (
    <li className="project-card" data-state={project.state}>
      <span className="project-card__badge">
        <Icon name={STATE_ICON[project.state] ?? "lightbulb"} size={14} />
        {t(`marketplace:state.${project.state}`)}
      </span>
      <h2 className="project-card__title">
        <Link to={`/projects/${project.id}`}>{project.title}</Link>
      </h2>
      <Stepper state={project.state} />
      <div className="project-card__figures">
        <span>
          <Icon name="coins" size={16} />
          <strong>{format.number(project.totals.reserved + project.totals.consumed)}</strong>
          {t("marketplace:projects.gathered")}
        </span>
        <span>
          <Icon name="users" size={16} />
          {t("marketplace:projects.funders", { count: project.totals.funders })}
        </span>
      </div>
      {project.accepts_funding ? (
        <Link className="ds-button ds-button--primary project-card__cta" to={`/projects/${project.id}`}>
          <Icon name="coins" size={16} />
          {t("marketplace:projects.fund")}
        </Link>
      ) : null}
    </li>
  );
}

export default function ProjectsPage() {
  const t = useT();
  const format = useFormat();
  const projects = useProjects();
  const fundings = useMyFundings();
  const [stage, setStage] = useState<string>("all");
  const list = projects.data ?? [];
  const shown = useMemo(
    () => (stage === "all" ? list : list.filter((p) => STAGES[stage]?.includes(p.state))),
    [list, stage],
  );
  const gathered = list.reduce((sum, p) => sum + p.totals.reserved + p.totals.consumed, 0);
  const mine = (fundings.data ?? []).reduce((sum, f) => sum + f.amount, 0);
  return (
    <div className="ds-stack projects-page">
      <PageHeader
        icon="lightbulb"
        title={t("marketplace:projects.title")}
        context={t("marketplace:projects.intro")}
      />
      <AdminStats
        label={t("marketplace:projects.title")}
        stats={[
          {
            key: "open",
            icon: "coins",
            label: t("marketplace:projects.statOpen"),
            value: format.number(list.filter((p) => p.state === "open").length),
          },
          {
            key: "building",
            icon: "wrench",
            label: t("marketplace:projects.statBuilding"),
            value: format.number(list.filter((p) => STAGES.building?.includes(p.state)).length),
          },
          {
            key: "released",
            icon: "rocket",
            label: t("marketplace:projects.statReleased"),
            value: format.number(list.filter((p) => p.state === "released").length),
          },
          {
            key: "gathered",
            icon: "users",
            label: t("marketplace:projects.statGathered"),
            value: format.number(gathered),
          },
          {
            key: "mine",
            icon: "heart",
            label: t("marketplace:projects.statMine"),
            value: format.number(mine),
          },
        ]}
      />
      <section className="project-launch-cta">
        <Icon name="lightbulb" size={32} />
        <div>
          <h2>{t("marketplace:projects.launchTitle")}</h2>
          <p>{t("marketplace:projects.launchHint")}</p>
        </div>
        <Link className="ds-button ds-button--primary" to="/marketplace?type=project_launch">
          <Icon name="shop" size={16} />
          {t("marketplace:projects.launch")}
        </Link>
      </section>
      <fieldset className="ds-subnav" aria-label={t("marketplace:projects.stages")}>
        {["all", ...Object.keys(STAGES)].map((key) => (
          <button key={key} type="button" aria-pressed={stage === key} onClick={() => setStage(key)}>
            {t(`marketplace:projects.stage.${key}`)}
            <span className="admin-tabs__count">
              {key === "all" ? list.length : list.filter((p) => STAGES[key]?.includes(p.state)).length}
            </span>
          </button>
        ))}
      </fieldset>
      {projects.isError ? <FunctionalState state="unavailable" onRetry={() => projects.refetch()} /> : null}
      {projects.data && !shown.length ? (
        <AdminEmpty icon="lightbulb" title={t("marketplace:projects.empty")} />
      ) : (
        <ul className="project-grid">
          {shown.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </ul>
      )}
      <MyFundings />
    </div>
  );
}
