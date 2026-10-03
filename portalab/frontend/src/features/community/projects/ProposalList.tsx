import { type FormEvent, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { useCreateProposal, useProposals } from "./api";
import { HelpWantedBadge } from "./HelpWantedBadge";

/** ``/community/proposals`` (spec 012 T024): open proposals, my proposals and a proposal form. */
export function ProposalList() {
  const t = useT();
  const open = useProposals();
  const mine = useProposals(true);
  const create = useCreateProposal();
  const canPropose = useHasPermission("community.propose");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [kind, setKind] = useState<"project" | "feature">("project");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { kind, title, body_md: body, tags: [] },
      {
        onSuccess: () => {
          setTitle("");
          setBody("");
        },
      },
    );
  };
  return (
    <div className="ds-stack">
      <section aria-labelledby="proposals-open" className="ds-stack">
        <h2 id="proposals-open">{t("community:proposals.title")}</h2>
        {open.isError ? <FunctionalState state="unavailable" onRetry={() => open.refetch()} /> : null}
        {open.data?.length === 0 ? <p>{t("community:proposals.empty")}</p> : null}
        <ul className="community-members">
          {(open.data ?? []).map((proposal) => (
            <li key={proposal.id} className="ds-card">
              <Link to={`/community/proposals/${proposal.id}`}>{proposal.title}</Link>
              <span className="community-meta">
                {t(`community:proposals.kind.${proposal.kind}`)} ·{" "}
                {t("community:proposals.votes", { count: proposal.votes })}
              </span>
              {proposal.help_wanted ? <HelpWantedBadge /> : null}
            </li>
          ))}
        </ul>
      </section>
      {(mine.data ?? []).length ? (
        <section aria-labelledby="proposals-mine" className="ds-stack">
          <h2 id="proposals-mine">{t("community:proposals.mine")}</h2>
          <ul className="community-members">
            {(mine.data ?? []).map((proposal) => (
              <li key={proposal.id}>
                <Link to={`/community/proposals/${proposal.id}`}>{proposal.title}</Link>{" "}
                <span className="community-meta">{t(`community:proposals.status.${proposal.status}`)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {canPropose ? (
        <form className="ds-card ds-stack" onSubmit={submit} aria-labelledby="proposals-new">
          <h2 id="proposals-new">{t("community:proposals.new")}</h2>
          <SelectField
            label={t("community:proposals.kindLabel")}
            value={kind}
            onChange={(e) => setKind(e.target.value as "project" | "feature")}
          >
            <option value="project">{t("community:proposals.kind.project")}</option>
            <option value="feature">{t("community:proposals.kind.feature")}</option>
          </SelectField>
          <TextField
            label={t("community:proposals.form.title")}
            value={title}
            required
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="ds-field">
            <label htmlFor="proposal-body">{t("community:proposals.form.body")}</label>
            <textarea
              id="proposal-body"
              rows={6}
              maxLength={20000}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          {create.isSuccess ? (
            <p role="status">
              {t(
                create.data?.status === "open"
                  ? "community:proposals.published"
                  : "community:proposals.pending",
              )}
            </p>
          ) : null}
          {create.isError ? <p role="alert">{t("community:proposals.error.generic")}</p> : null}
          <Button type="submit" disabled={create.isPending || !title.trim()}>
            {t("community:proposals.submit")}
          </Button>
        </form>
      ) : null}
    </div>
  );
}
