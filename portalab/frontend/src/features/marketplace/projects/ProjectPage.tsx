import { Link, useParams } from "react-router";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useProject } from "../api";
import { FundingPanel } from "./FundingPanel";
import { Timeline } from "./Timeline";
import "../marketplace.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/** ``/projects/:projectId`` (spec 015 T014): state timeline, published rules and funding. */
export function ProjectPage() {
  const t = useT();
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  if (project.isPending) return <FunctionalState state="loading" />;
  if (project.isError || !project.data)
    return <FunctionalState state="unavailable" onRetry={() => project.refetch()} />;
  const data = project.data;
  return (
    <div className="ds-stack">
      <PageHeader icon="lightbulb" title={data.title} />
      <p>
        {t("marketplace:project.state", { state: t(`marketplace:state.${data.state}`) })} ·{" "}
        <Link to={`/community/proposals/${data.proposal_ref}`}>{t("marketplace:project.proposal")}</Link>
      </p>
      <FundingPanel project={data} />
      <Timeline project={data} />
    </div>
  );
}
