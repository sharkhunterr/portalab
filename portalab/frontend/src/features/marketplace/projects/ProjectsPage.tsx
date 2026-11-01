import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { AdminEmpty } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Project, useMyFundings, useProjects, useProjectsSeen } from "../api";
import { MyFundings } from "./MyFundings";
import { Gathered, STAGES, STATE_ICON, Stepper } from "./parts";
import "../marketplace.css";

/** A project as a card — marked when it moved since my last visit. */
function ProjectCard({ project, fresh }: { project: Project; fresh: boolean }) {
  const t = useT();
  const format = useFormat();
  return (
    <li className="project-card" data-state={project.state} data-fresh={fresh || undefined}>
      <div className="project-card__head">
        <span className="project-card__badge">
          <Icon name={STATE_ICON[project.state] ?? "lightbulb"} size={14} />
          {t(`marketplace:state.${project.state}`)}
        </span>
        {fresh ? <span className="project-card__fresh">{t("marketplace:projects.new")}</span> : null}
      </div>
      <h2 className="project-card__title">
        <Link to={`/projects/${project.id}`}>{project.title}</Link>
      </h2>
      <Stepper state={project.state} />
      <Gathered project={project} />
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
      ) : (
        <Link className="ds-button ds-button--ghost project-card__cta" to={`/projects/${project.id}`}>
          {t("marketplace:projects.view")}
          <Icon name="chevron-right" size={16} />
        </Link>
      )}
    </li>
  );
}

/**
 * ``/projects`` (spec 015 slice A; 027, issue 303 redesign): community projects as cards — where each one is
 * on its way (idea → released, in words), what it gathered toward its goal and from how many members, what
 * moved since my last visit marked — filtered by stage, with the key figures in one line, a way to launch
 * one (a shop purchase) and my fundings. Opening it reads what was new (the navigation's badge goes).
 */
export default function ProjectsPage() {
  const t = useT();
  const format = useFormat();
  const projects = useProjects();
  const fundings = useMyFundings();
  const seen = useProjectsSeen();
  const [stage, setStage] = useState<string>("all");
  // issue 303: when I had last looked (null: never) — what changed after is marked, for this visit
  const [since, setSince] = useState<string | null | undefined>(undefined);
  const loaded = projects.isSuccess;
  // biome-ignore lint/correctness/useExhaustiveDependencies: once per visit, when the projects are shown
  useEffect(() => {
    if (loaded) seen.mutate(undefined, { onSuccess: (previous) => setSince(previous ?? null) });
  }, [loaded]);
  const list = projects.data ?? [];
  const shown = useMemo(
    () => (stage === "all" ? list : list.filter((p) => STAGES[stage]?.includes(p.state))),
    [list, stage],
  );
  const fresh = (project: Project) =>
    since !== undefined &&
    project.state !== "idea" &&
    (since === null || new Date(project.updated_at) > new Date(since));
  const gathered = list.reduce((sum, p) => sum + p.totals.reserved + p.totals.consumed, 0);
  const mine = (fundings.data ?? []).reduce((sum, f) => sum + f.amount, 0);
  const figures = [
    { key: "open", icon: "coins", value: list.filter((p) => p.state === "open").length },
    { key: "building", icon: "wrench", value: list.filter((p) => STAGES.building?.includes(p.state)).length },
    { key: "released", icon: "rocket", value: list.filter((p) => p.state === "released").length },
    { key: "gathered", icon: "users", value: gathered },
    { key: "mine", icon: "heart", value: mine },
  ];
  const statKey: Record<string, string> = {
    open: "statOpen",
    building: "statBuilding",
    released: "statReleased",
    gathered: "statGathered",
    mine: "statMine",
  };
  return (
    <div className="ds-stack projects-page">
      <PageHeader
        icon="lightbulb"
        title={t("marketplace:projects.title")}
        context={t("marketplace:projects.intro")}
      />
      <dl className="projects-figures" aria-label={t("marketplace:projects.figures")}>
        {figures.map((figure) => (
          <div key={figure.key}>
            <dt>
              <Icon name={figure.icon} size={14} />
              {t(`marketplace:projects.${statKey[figure.key]}`)}
            </dt>
            <dd>{format.number(figure.value)}</dd>
          </div>
        ))}
      </dl>
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
            <ProjectCard key={project.id} project={project} fresh={fresh(project)} />
          ))}
        </ul>
      )}
      <section className="project-launch-cta">
        <Icon name="lightbulb" size={24} />
        <div>
          <h2>{t("marketplace:projects.launchTitle")}</h2>
          <p>{t("marketplace:projects.launchHint")}</p>
        </div>
        <Link className="ds-button ds-button--primary" to="/marketplace?type=project_launch">
          <Icon name="shop" size={16} />
          {t("marketplace:projects.launch")}
        </Link>
      </section>
      <MyFundings />
    </div>
  );
}
