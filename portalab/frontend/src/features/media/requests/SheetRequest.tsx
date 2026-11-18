import { useLocation } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { type RequestCard, useRequestList } from "./api";

/**
 * Issue 498: a book's, a game's sheet (a title the library lacks) knows the member asked for it — from this
 * very sheet: its badge says where the request stands, its journey follows (RequestJourney), and no second
 * « Ask for it » while it is open. A cancelled request is forgotten; a declined one leaves asking again.
 */
const ENDED = ["declined", "failed", "cancelled"];
const ICONS: Record<string, string> = {
  pending: "hourglass",
  with_team: "users",
  available: "check",
  declined: "blocked",
  failed: "blocked",
};

export function useSheetRequests(): { latest: RequestCard | undefined; asked: (kind: string) => boolean } {
  const location = useLocation();
  const here = `${location.pathname}${location.search}`;
  const list = useRequestList();
  // the latest first, as « My requests » lists them
  const mine = (list.data ?? []).filter((r) => r.sheet === here && r.state !== "cancelled");
  return {
    latest: mine[0],
    asked: (kind) => mine.some((r) => r.kind === kind && !ENDED.includes(r.state)),
  };
}

export function SheetRequestBadge({ card }: { card: RequestCard }) {
  const t = useT();
  const stage = card.stage ?? card.state;
  const tone = ENDED.includes(stage) ? "unavailable" : stage === "available" ? "available" : "requested";
  return (
    <span className="media-badge" data-tone={tone}>
      <Icon name={ICONS[stage] ?? "inbox"} size={14} />
      {t(`media:myRequests.stage.${stage}`, { percent: Math.round((card.progress ?? 0) * 100), date: "" })}
    </span>
  );
}
