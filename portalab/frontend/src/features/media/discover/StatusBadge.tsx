import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { Requestable } from "./api";

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
