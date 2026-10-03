import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { SelectField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Proposal, useParticipations, useProposalActions } from "./api";

const ROLES = ["contributor", "tester", "helper"] as const;

/**
 * Participation (spec 012 T026): take part as contributor, tester or helper; the proposer recognizes a
 * participation once (it becomes Contribution through Gamification). No messaging is involved.
 */
export function ParticipationPanel({
  proposal,
  canRecognize,
}: {
  proposal: Proposal;
  canRecognize: boolean;
}) {
  const t = useT();
  const participations = useParticipations(proposal.id);
  const actions = useProposalActions(proposal.id);
  const [role, setRole] = useState<(typeof ROLES)[number]>("contributor");
  const mine = (participations.data ?? []).some((p) => p.mine);
  const error = actions.recognize.error instanceof ApiError ? actions.recognize.error.code : null;
  return (
    <section aria-labelledby="proposal-participation" className="ds-card ds-stack">
      <h2 id="proposal-participation">{t("community:participation.title")}</h2>
      <ul className="ds-stack">
        {(participations.data ?? []).map((p) => (
          <li key={p.id} className="ds-stack--row">
            <span>
              {p.member?.display_name ?? t("community:feed.someone")} ·{" "}
              {t(`community:participation.role.${p.role}`)}
              {p.recognized ? ` · ${t("community:participation.recognized")}` : ""}
            </span>
            {canRecognize && !p.mine && !p.recognized ? (
              <Button variant="secondary" onClick={() => actions.recognize.mutate(p.id)}>
                {t("community:participation.recognize")}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {error ? (
        <p role="alert">{t(`community:participation.error.${error.split(".")[1] ?? "generic"}`)}</p>
      ) : null}
      {proposal.status === "open" ? (
        mine ? (
          <Button variant="secondary" onClick={() => actions.leave.mutate()}>
            {t("community:participation.leave")}
          </Button>
        ) : (
          <div className="ds-stack--row">
            <SelectField
              label={t("community:participation.as")}
              value={role}
              onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}
            >
              {ROLES.map((value) => (
                <option key={value} value={value}>
                  {t(`community:participation.role.${value}`)}
                </option>
              ))}
            </SelectField>
            <Button onClick={() => actions.participate.mutate(role)}>
              {t("community:participation.join")}
            </Button>
          </div>
        )
      ) : null}
    </section>
  );
}
