import { CountBadge } from "../../design-system/components/CountBadge";
import { useT } from "../../i18n/hooks/useT";
import { useAttention } from "./attention";

/** #98: something waits for me somewhere in the navigation — a dot on the button that opens it. */
export function MenuWaiting() {
  const t = useT();
  const attention = useAttention();
  const total = Object.values(attention.counts).reduce((sum, n) => sum + n, 0);
  return <CountBadge count={total} dot label={t("shell:attention", { count: total })} />;
}
