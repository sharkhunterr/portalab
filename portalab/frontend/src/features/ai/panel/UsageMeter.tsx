import * as PopoverPrimitive from "@radix-ui/react-popover";
import type { CSSProperties } from "react";
import { Link } from "react-router";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";

export interface Usage {
  budget: number;
  used: number;
  recharge?: number | undefined;
  shop?: boolean | undefined;
  /** issue 173: the capacities bought — until when (ISO time, « forever ») */
  perks?: Record<string, string> | undefined;
}

const PERK_WORDS: Record<string, string> = {
  daily_tokens: "daily",
  model: "model",
  reflection: "reflection",
  context: "context",
  tools: "tools",
};

/** The next midnight UTC — when the day's allowance starts again. */
function nextReset(): Date {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));
}

/**
 * Issue 179 — in the window's header: how much of today's allowance the member used (a small ring and a
 * share); pressed, a few words more — tokens used of the day's, the reserve bought, the capacities held and
 * until when, when the day starts again, and where to get more.
 */
export function UsageMeter({ usage }: { usage: Usage }) {
  const t = useT();
  const format = useFormat();
  // issue 180: what can be used today — the day's allowance (or what went past it, taken from the reserve)
  // and the reserve still held; full only once both are spent
  const reserve = Math.max(0, usage.recharge ?? 0);
  const total = Math.max(usage.budget, usage.used) + reserve;
  const share = total > 0 ? usage.used / total : 0;
  const percent = Math.min(100, Math.round(share * 100));
  const tone = share >= 1 ? "over" : share >= 0.85 ? "low" : "ok";
  const label = t("ai:usage.label", { percent });
  const perks = Object.entries(usage.perks ?? {}).filter(([perk]) => perk in PERK_WORDS);
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>
        <button type="button" className="ai-usage" data-tone={tone} aria-label={label} title={label}>
          <span
            className="ai-usage__ring"
            aria-hidden="true"
            style={{ "--ai-usage": `${percent}%` } as CSSProperties}
          />
          <span className="ai-usage__value">{percent} %</span>
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          className="ds-popover ai-usage__pop"
          aria-label={t("ai:usage.title")}
          sideOffset={6}
          align="end"
          data-tone={tone}
          // issue 181: a guided tour showing these details leaves them open
          onInteractOutside={(event) => {
            if (document.querySelector(".tour")) event.preventDefault();
          }}
        >
          <p className="ai-usage__title">{t("ai:usage.title")}</p>
          <span className="ai-usage__bar" aria-hidden="true">
            <span style={{ inlineSize: `${percent}%` }} />
          </span>
          <dl className="ai-usage__facts">
            <dt>{t("ai:usage.used")}</dt>
            <dd>
              {t("ai:usage.usedOf", {
                used: format.compact(usage.used),
                budget: format.compact(total),
                percent: Math.round(share * 100),
              })}
            </dd>
            <dt>{t("ai:usage.day")}</dt>
            <dd>
              {usage.used >= usage.budget
                ? t("ai:usage.dayUsedUp", { budget: format.compact(usage.budget) })
                : t("ai:usage.dayLeft", {
                    left: format.compact(usage.budget - usage.used),
                    budget: format.compact(usage.budget),
                  })}
            </dd>
            {reserve ? (
              <>
                <dt>{t("ai:usage.reserve")}</dt>
                <dd>{t("ai:usage.reserveLeft", { amount: format.compact(reserve) })}</dd>
              </>
            ) : null}
            <dt>{t("ai:usage.reset")}</dt>
            <dd>{format.dateTime(nextReset())}</dd>
          </dl>
          {perks.length ? (
            <>
              <p className="ai-usage__subtitle">{t("ai:usage.perks")}</p>
              <ul className="ai-usage__perks">
                {perks.map(([perk, until]) => (
                  <li key={perk}>
                    {t(`ai:usage.perk.${PERK_WORDS[perk]}`)}
                    {" — "}
                    {until === "forever"
                      ? t("ai:usage.forever")
                      : t("ai:usage.until", { when: format.dateTime(until) })}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <p className="ai-usage__hint">{t("ai:usage.hint")}</p>
          {usage.shop ? (
            <PopoverPrimitive.Close asChild>
              <Link className="ai-usage__shop" to="/marketplace?type=ai_capacity">
                {t("ai:panel.moreInShop")}
              </Link>
            </PopoverPrimitive.Close>
          ) : null}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
