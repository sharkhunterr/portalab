import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { Requestable } from "./api";
import "./status.css";

/** Where a title stands for someone about to ask for it — in words, with a tone. */
export function StatusBadge({ item }: { item: Pick<Requestable, "status" | "request"> }) {
  const t = useT();
  const key = item.request ? (item.request.mine ? "mine" : "asked") : item.status;
  if (key === "unknown") return null;
  return (
    <span className="discover-status" data-status={key}>
      <Icon
        name={
          key === "available" ? "check" : key === "partial" ? "list" : key === "mine" ? "inbox" : "hourglass"
        }
        size={12}
      />
      {t(`media:discover.status.${key}`)}
    </span>
  );
}

/** #92: the badge on a poster's corner, for any title: ``available``, ``requested`` (a request in
 * progress), ``mine`` (asked for by the member); nothing otherwise — « not available » helps nobody. */
export function PosterBadge({ status }: { status: string | null | undefined }) {
  if (status !== "available" && status !== "requested" && status !== "mine") return null;
  return (
    <span className="discover-card__badge">
      <StatusBadge
        item={{
          status: status === "available" ? "available" : "pending",
          request: status === "mine" ? { mine: true } : null,
        }}
      />
    </span>
  );
}
