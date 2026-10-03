import { Badge } from "../../../design-system/components/Content";
import { useT } from "../../../i18n/hooks/useT";

/** "Help wanted" in text (never color alone), with the proposer's note rendered as plain text. */
export function HelpWantedBadge({ note }: { note?: string | null }) {
  const t = useT();
  return (
    <span className="ds-stack--row">
      <Badge tone="partial">{t("community:proposals.helpWanted")}</Badge>
      {note ? <span>{note}</span> : null}
    </span>
  );
}
