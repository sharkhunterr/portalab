import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useId, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { useLogout } from "../auth/useAuth";
import { MY_TERMS_KEY, type MyTerms, TERMS_REQUIRED_EVENT, useAcceptTerms, useMyTerms } from "./api";
import "../content/content.css";
import "./terms.css";

/**
 * Terms of use gate (027): while the member has not accepted the version in force, a small window at the
 * bottom of the screen asks them — accept, refuse (which signs out), or read the terms in a modal first.
 * The portal stays closed meanwhile (the server refuses everything else: ``terms.acceptance_required``); a
 * refusal seen later (a version published while the member is here) brings the window back.
 */
export function TermsGate({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const standing = useMyTerms();
  useEffect(() => {
    const again = () => void client.invalidateQueries({ queryKey: MY_TERMS_KEY });
    window.addEventListener(TERMS_REQUIRED_EVENT, again);
    return () => window.removeEventListener(TERMS_REQUIRED_EVENT, again);
  }, [client]);
  if (standing.isPending) return null;
  if (standing.data?.required && standing.data.terms) return <TermsPrompt standing={standing.data} />;
  return <>{children}</>;
}

export function TermsPrompt({ standing }: { standing: MyTerms }) {
  const t = useT();
  const format = useFormat();
  const titleId = useId();
  const accept = useAcceptTerms();
  const logout = useLogout();
  const [reading, setReading] = useState(false);
  const [refusing, setRefusing] = useState(false);
  const terms = standing.terms;
  if (!terms) return null;
  const outdated = accept.error instanceof ApiError && accept.error.code === "terms.outdated";
  const version = t("shell:terms.version", {
    version: terms.version,
    date: format.date(terms.published_at, "long"),
  });
  const actions = (
    <>
      <Button variant="ghost" onClick={() => setRefusing(true)} disabled={logout.isPending}>
        {t("shell:terms.refuse")}
      </Button>
      <Button onClick={() => accept.mutate(terms.version)} disabled={accept.isPending}>
        <Icon name="check" size={16} />
        {t("shell:terms.acceptShort")}
      </Button>
    </>
  );
  return (
    <div className="terms-wait">
      <section className="terms-prompt" role="alertdialog" aria-labelledby={titleId}>
        <span className="terms-prompt__seal" aria-hidden="true">
          <Icon name="shield" size={22} />
        </span>
        <div className="terms-prompt__text">
          <h2 id={titleId}>
            {standing.accepted_version ? t("shell:terms.promptNew") : t("shell:terms.promptFirst")}
          </h2>
          <p className="terms-prompt__meta">{version}</p>
          <p>
            {standing.accepted_version
              ? t("shell:terms.updated", { version: standing.accepted_version })
              : t("shell:terms.first")}
          </p>
          {terms.summary ? <p className="terms-prompt__summary">{terms.summary}</p> : null}
          {accept.isError ? (
            <p role="alert" className="terms-prompt__error">
              {outdated ? t("shell:terms.outdated") : t("shell:terms.failed")}
            </p>
          ) : null}
        </div>
        {refusing ? (
          <div className="terms-prompt__actions" data-refusing="">
            <p className="terms-prompt__warn">{t("shell:terms.refuseConfirm")}</p>
            <Button variant="ghost" onClick={() => setRefusing(false)}>
              {t("shell:terms.back")}
            </Button>
            <Button variant="danger" onClick={() => logout.mutate()} disabled={logout.isPending}>
              <Icon name="logout" size={16} />
              {t("shell:terms.refuseYes")}
            </Button>
          </div>
        ) : (
          <div className="terms-prompt__actions">
            <Dialog
              size="lg"
              open={reading}
              onOpenChange={setReading}
              title={terms.title}
              description={version}
              closeLabel={t("shell:terms.close")}
              trigger={
                <Button variant="secondary">
                  <Icon name="scroll" size={16} />
                  {t("shell:terms.readButton")}
                </Button>
              }
              footer={actions}
            >
              {terms.summary ? (
                <aside className="terms-prompt__changes">
                  <strong>{t("shell:terms.changes")}</strong>
                  <p>{terms.summary}</p>
                </aside>
              ) : null}
              <div
                className="content-body terms-prompt__doc"
                // biome-ignore lint/security/noDangerouslySetInnerHtml: server-sanitized by the single Markdown pipeline (nh3 allowlist)
                dangerouslySetInnerHTML={{ __html: terms.html }}
              />
            </Dialog>
            {actions}
          </div>
        )}
        <p className="terms-prompt__fine">{t("shell:terms.refuseHint")}</p>
      </section>
    </div>
  );
}
