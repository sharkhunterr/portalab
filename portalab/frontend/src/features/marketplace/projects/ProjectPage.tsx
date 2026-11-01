import { Link, useParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { CurrencyShort } from "../../../design-system/site/SiteLook";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { MemberAvatar } from "../../community/MemberFace";
import { type Project, type ProjectFunder, useProject, useProjectFunders } from "../api";
import { FundingPanel, FundingProgress } from "./FundingPanel";
import { STATE_ICON } from "./parts";
import { Timeline } from "./Timeline";
import "../marketplace.css";

/** issue 304: who backs the project, the largest first — a member who stays anonymous without a name. */
function Funders({ funders }: { funders: ProjectFunder[] }) {
  const t = useT();
  const format = useFormat();
  return (
    <section aria-labelledby="project-funders" className="project-funders">
      <h2 id="project-funders">
        <Icon name="users" size={18} /> {t("marketplace:funders.title", { count: funders.length })}
      </h2>
      {funders.length ? (
        <ol>
          {funders.map((funder, index) => (
            <li key={funder.user_id ?? `anonymous-${index}`} data-me={funder.me || undefined}>
              <MemberAvatar
                id={funder.user_id ?? `anonymous-${index}`}
                name={funder.name ?? t("marketplace:funders.anonymous")}
                anonymous={!funder.user_id}
              />
              <span className="project-funders__who">
                <strong>{funder.name ?? t("marketplace:funders.anonymous")}</strong>
                {funder.me ? (
                  <span className="project-funders__you">{t("marketplace:funders.you")}</span>
                ) : null}
                <small>{t("marketplace:funders.since", { date: format.date(funder.since) })}</small>
              </span>
              <span className="project-funders__amount">
                {format.number(funder.amount)}
                <CurrencyShort />
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="project-funders__empty">{t("marketplace:funders.empty")}</p>
      )}
    </section>
  );
}

/** The notes the team left along the way (the pitch first), each with its step. */
function Notes({ project }: { project: Project }) {
  const t = useT();
  const format = useFormat();
  const notes = project.notes ?? [];
  return notes.length ? (
    <section aria-labelledby="project-notes" className="project-notes">
      <h2 id="project-notes">
        <Icon name="message" size={18} /> {t("marketplace:project.notes")}
      </h2>
      <ul>
        {notes.map((note) => (
          <li key={`${note.state}-${note.at}`}>
            <span className="project-notes__step">
              <Icon name={STATE_ICON[note.state] ?? "lightbulb"} size={14} />
              {t(`marketplace:state.${note.state}`)} · {format.date(note.at)}
            </span>
            <p>{note.note}</p>
          </li>
        ))}
      </ul>
    </section>
  ) : null;
}

/**
 * ``/projects/:projectId`` (spec 015 T014; issue 304 redesign): the project's way as a horizontal timeline,
 * where its funding stands (gathered, its goal, what is left), a way to contribute, who backs it, and the
 * notes left along the way.
 */
export function ProjectPage() {
  const t = useT();
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const funders = useProjectFunders(projectId);
  if (project.isPending) return <FunctionalState state="loading" />;
  if (project.isError || !project.data)
    return <FunctionalState state="unavailable" onRetry={() => project.refetch()} />;
  const data = project.data;
  const backers = funders.data ?? [];
  const mine = backers.find((f) => f.me)?.amount ?? 0;
  return (
    <div className="ds-stack project-page" data-state={data.state}>
      <PageHeader icon="lightbulb" title={data.title} />
      <p className="project-page__meta">
        <span className="project-card__badge">
          <Icon name={STATE_ICON[data.state] ?? "lightbulb"} size={14} />
          {t(`marketplace:state.${data.state}`)}
        </span>
        <Link to={`/community/proposals/${data.proposal_ref}`}>
          {t("marketplace:project.proposal")}
          <Icon name="chevron-right" size={14} />
        </Link>
      </p>
      <Timeline project={data} />
      <div className="project-page__funding">
        <FundingProgress project={data} mine={mine} />
        <FundingPanel project={data} mine={mine} />
      </div>
      <Funders funders={backers} />
      <Notes project={data} />
    </div>
  );
}
