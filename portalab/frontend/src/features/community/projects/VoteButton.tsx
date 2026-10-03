import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Proposal, useProposalActions } from "./api";

/** Free up-vote of support (spec 012 T024): one per active account; the count is public, voters are not. */
export function VoteButton({ proposal }: { proposal: Proposal }) {
  const t = useT();
  const { vote } = useProposalActions(proposal.id);
  const closed =
    proposal.status !== "open" || (proposal.lifecycle as { state?: string }).state === "validation";
  const error = vote.error instanceof ApiError ? vote.error.code : null;
  return (
    <div className="ds-stack--row">
      <Button
        aria-pressed={proposal.my_vote}
        disabled={closed || vote.isPending}
        onClick={() => vote.mutate(!proposal.my_vote)}
      >
        {proposal.my_vote ? t("community:proposals.unvote") : t("community:proposals.vote")}
      </Button>
      <span>{t("community:proposals.votes", { count: proposal.votes })}</span>
      {error ? (
        <span role="alert">
          {t(`community:proposals.error.${error === "community.voting_closed" ? "closed" : "generic"}`)}
        </span>
      ) : null}
    </div>
  );
}
