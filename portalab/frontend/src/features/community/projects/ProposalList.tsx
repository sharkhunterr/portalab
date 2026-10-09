import { type FormEvent, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { EmptyState } from "../../../design-system/components/Placeholders";
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
  const [writing, setWriting] = useState(false);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { kind, title, body_md: body, tags: [] },
      {
        onSuccess: () => {
          setTitle("");
          setBody("");
          setWriting(false);
        },
      },
    );
  };
  return (
    <div className="ds-stack">
      {canPropose ? (
        <div className="community-actions">
          <Dialog
            open={writing}
            onOpenChange={setWriting}
            title={t("community:proposals.new")}
            closeLabel={t("community:proposals.close")}
            size="lg"
            trigger={
              <Button>
                <Icon name="plus" size={16} />
                {t("community:proposals.new")}
              </Button>
            }
          >
            <form className="ds-stack" onSubmit={submit}>
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
              {create.isError ? <p role="alert">{t("community:proposals.error.generic")}</p> : null}
              <DialogActions>
                <Button type="submit" disabled={create.isPending || !title.trim()}>
                  {t("community:proposals.submit")}
                </Button>
              </DialogActions>
            </form>
          </Dialog>
        </div>
      ) : null}
      {create.isSuccess ? (
        <p role="status" className="community-notice">
          {t(
            create.data?.status === "open" ? "community:proposals.published" : "community:proposals.pending",
          )}
        </p>
      ) : null}
      <section aria-labelledby="proposals-open" className="ds-stack">
        <h2 id="proposals-open" className="community-subtitle">
          {t("community:proposals.title")}
        </h2>
        {open.isError ? <FunctionalState state="unavailable" onRetry={() => open.refetch()} /> : null}
        {open.data?.length === 0 ? (
          <EmptyState
            icon="lightbulb"
            title={t("community:proposals.empty")}
            action={
              <Link className="ds-button ds-button--secondary" to="/projects">
                {t("community:proposals.toProjects")}
              </Link>
            }
          />
        ) : null}
        <ul className="community-proposals">
          {(open.data ?? []).map((proposal) => (
            <li key={proposal.id}>
              <Link to={`/community/proposals/${proposal.id}`} className="community-proposal">
                <span className="community-proposal__votes">
                  <Icon name="arrow-up" size={16} />
                  <strong>{proposal.votes}</strong>
                </span>
                <span className="community-proposal__text">
                  <strong>{proposal.title}</strong>
                  <span className="community-meta">
                    {t(`community:proposals.kind.${proposal.kind}`)} ·{" "}
                    {t("community:proposals.votes", { count: proposal.votes })}
                  </span>
                </span>
                {proposal.help_wanted ? <HelpWantedBadge /> : null}
              </Link>
            </li>
          ))}
        </ul>
      </section>
      {(mine.data ?? []).length ? (
        <section aria-labelledby="proposals-mine" className="ds-stack">
          <h2 id="proposals-mine" className="community-subtitle">
            {t("community:proposals.mine")}
          </h2>
          <ul className="community-proposals">
            {(mine.data ?? []).map((proposal) => (
              <li key={proposal.id}>
                <Link to={`/community/proposals/${proposal.id}`} className="community-proposal">
                  <span className="community-proposal__text">
                    <strong>{proposal.title}</strong>
                  </span>
                  <span className="ds-badge">{t(`community:proposals.status.${proposal.status}`)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
