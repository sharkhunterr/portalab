import { type ReactElement, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { useAskOptions } from "./api";
import { AskForm, type AskStart } from "./RequestsPage";

/**
 * Issue 377: asking the team for a title in a dialog, over the page one is on — as a film is asked for —
 * the form filled from the sheet, the title told absent or the words searched. Nothing while the requests
 * are switched off or take no kind of title.
 */
export function AskDialog({ start, trigger }: { start: AskStart; trigger: ReactElement }) {
  const t = useT();
  const options = useAskOptions();
  const [open, setOpen] = useState(false);
  const [round, setRound] = useState(0); // a fresh form each time it opens
  if (!options.data?.kinds.length) return null;
  return (
    <Dialog
      trigger={trigger}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setRound((n) => n + 1);
      }}
      title={start.title ? t("media:discover.askTitle", { title: start.title }) : t("media:ask.page.title")}
      closeLabel={t("media:discover.close")}
      size="lg"
      footer={
        <Link className="ds-button ds-button--secondary" to="/media/requests" onClick={() => setOpen(false)}>
          <Icon name="inbox" size={16} />
          {t("media:ask.seeMine")}
        </Link>
      }
    >
      <AskForm key={round} kinds={options.data.kinds} start={start} bare />
    </Dialog>
  );
}
