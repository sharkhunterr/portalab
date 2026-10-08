import { useEffect, useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { SafeHtml } from "../content/SafeHtml";
import { useMyTerms } from "./api";
import "./terms.css";

/**
 * The terms of use in force, read again in a modal (027) — opened from the profile menu (``openTermsViewer``)
 * wherever the member is, with the version they accepted. Mounted once by the shell.
 */
const OPEN_EVENT = "portalab:terms-open";

export function openTermsViewer(): void {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

export function TermsViewer() {
  const t = useT();
  const format = useFormat();
  const [open, setOpen] = useState(false);
  const mine = useMyTerms(open);
  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(OPEN_EVENT, show);
    return () => window.removeEventListener(OPEN_EVENT, show);
  }, []);
  const terms = mine.data?.terms;
  return (
    <Dialog
      size="lg"
      open={open}
      onOpenChange={setOpen}
      title={terms?.title ?? t("shell:terms.title")}
      {...(terms
        ? {
            description: t("shell:terms.version", {
              version: terms.version,
              date: format.date(terms.published_at, "long"),
            }),
          }
        : {})}
      closeLabel={t("shell:terms.close")}
      trigger={<span hidden />}
    >
      <div className="terms-viewer">
        {mine.data && !terms ? <p className="terms-page__none">{t("shell:terms.none")}</p> : null}
        {mine.data?.accepted_version && mine.data.accepted_at ? (
          <p className="terms-page__accepted">
            {t("shell:terms.accepted", {
              version: mine.data.accepted_version,
              date: format.date(mine.data.accepted_at, "long"),
            })}
          </p>
        ) : null}
        {terms ? <SafeHtml html={terms.html} diagrams={false} /> : null}
      </div>
    </Dialog>
  );
}

/** The profile menu's entry (a list item) — shown only while terms are in force. */
export function TermsMenuEntry({ onOpen }: { onOpen?: (() => void) | undefined }) {
  const t = useT();
  const mine = useMyTerms();
  if (!mine.data?.terms) return null;
  return (
    <li>
      <button
        type="button"
        onClick={() => {
          onOpen?.();
          openTermsViewer();
        }}
      >
        <Icon name="shield" size={16} />
        {t("shell:terms.link")}
      </button>
    </li>
  );
}
