import { Icon } from "../../design-system/components/Icon";
import { Popover } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";

/**
 * #99 — a look won (a booster, a gift) that may not be worn yet: its level, or Contribution, is not reached.
 * It shows among the member's looks, locked, with what it waits for — a padlock and « Lv 7 », which opens
 * a bubble saying why (on a tap as on a click: a hover tooltip never opens on a phone). 028: an owned look whose
 * visual pack is switched off shows the same way, « currently unavailable » (it comes back with its pack).
 */
export interface Waiting {
  level?: number;
  contribution?: number;
  /** 028: owned, but its visual pack is switched off — « currently unavailable », back with its pack */
  unavailable?: number;
}

export function waitingIn(
  list: ReadonlyArray<{ key: string; waiting?: Waiting | null }> | undefined,
  key: string,
): Waiting | undefined {
  return list?.find((choice) => choice.key === key)?.waiting ?? undefined;
}

export function WaitingTag({ waiting }: { waiting: Waiting }) {
  const t = useT();
  const short = waiting.unavailable
    ? t("community:looks.waiting.unavailableShort")
    : waiting.level
      ? t("community:looks.waiting.levelShort", { level: waiting.level })
      : t("community:looks.waiting.contributionShort", { amount: waiting.contribution ?? 0 });
  const why = waiting.unavailable
    ? t("community:looks.waiting.unavailable")
    : waiting.level
      ? t("community:looks.waiting.level", { level: waiting.level })
      : t("community:looks.waiting.contribution", { amount: waiting.contribution ?? 0 });
  return (
    <Popover
      label={why}
      trigger={
        <button
          type="button"
          className="look-waiting"
          aria-label={why}
          onClick={(event) => event.stopPropagation()}
        >
          <Icon name={waiting.unavailable ? "pause" : "lock"} size={12} />
          <span aria-hidden="true">{short}</span>
        </button>
      }
    >
      <p className="look-waiting__why">
        <Icon name="lock" size={14} />
        {why}
      </p>
    </Popover>
  );
}
