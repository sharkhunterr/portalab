import { Link, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { SafeHtml } from "../../content/SafeHtml";
import { useProposal, useProposalActions } from "./api";
import { HelpWantedBadge } from "./HelpWantedBadge";
import { ParticipationPanel } from "./ParticipationPanel";
import { VoteButton } from "./VoteButton";

interface Lifecycle {
  state?: string;
  project_id?: string;
  accepts_funding?: boolean;
  reserved?: number;
  funders?: number;
}

/**
 * ``/community/proposals/:proposalId`` (spec 012 T024): the proposal, its free vote, participation and
 * the lifecycle state read from Marketplace (icon + text); funding happens in the 015 flow (link).
 */
export function ProposalDetail() {
  const t = useT();
  const format = useFormat();
  const { proposalId = "" } = useParams();
  const proposal = useProposal(proposalId);
  const actions = useProposalActions(proposalId);
  const moderator = useHasPermission("community.moderate");
  if (proposal.isPending) return <FunctionalState state="loading" />;
  if (proposal.isError || !proposal.data) {
    return (
      <div className="ds-stack">
        <p>{t("community:proposals.notFound")}</p>
        <Link to="/community/proposals">{t("community:proposals.back")}</Link>
      </div>
    );
  }
  const data = proposal.data;
  const lifecycle = data.lifecycle as Lifecycle;
  return (
    <div className="ds-stack">
      <h1>{data.title}</h1>
      <p className="community-meta">
        {t(`community:proposals.kind.${data.kind}`)} · {t(`community:proposals.status.${data.status}`)}
        {data.proposer ? ` · ${data.proposer.display_name ?? ""}` : ""} · {format.date(data.created_at)}
      </p>
      {data.help_wanted ? <HelpWantedBadge note={data.help_note} /> : null}
      <SafeHtml html={data.rendered_html} diagrams={false} />
      <VoteButton proposal={data} />
      {lifecycle.state && lifecycle.state !== "none" ? (
        <section aria-labelledby="proposal-lifecycle" className="ds-card ds-stack">
          <h2 id="proposal-lifecycle">{t("community:proposals.lifecycle")}</h2>
          {lifecycle.state === "unavailable" ? (
            <FunctionalState state="unavailable" label={t("community:proposals.lifecycleUnavailable")} />
          ) : (
            <>
              <FunctionalState state="available" label={t(`marketplace:state.${lifecycle.state}`)} />
              <p>
                {t("community:proposals.funding", {
                  reserved: format.number(lifecycle.reserved ?? 0),
                  funders: lifecycle.funders ?? 0,
                })}
              </p>
              {lifecycle.project_id ? (
                <Link to={`/projects/${lifecycle.project_id}`}>
                  {lifecycle.accepts_funding
                    ? t("community:proposals.fund")
                    : t("community:proposals.project")}
                </Link>
              ) : null}
            </>
          )}
        </section>
      ) : null}
      <ParticipationPanel proposal={data} canRecognize={data.mine || moderator} />
      {data.mine && data.status === "open" ? (
        <div className="ds-stack--row">
          <Button
            variant="secondary"
            onClick={() => actions.help.mutate({ help_wanted: !data.help_wanted, note: data.help_note })}
          >
            {data.help_wanted ? t("community:proposals.helpOff") : t("community:proposals.helpOn")}
          </Button>
          <Button variant="secondary" onClick={() => actions.withdraw.mutate()}>
            {t("community:proposals.withdraw")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
