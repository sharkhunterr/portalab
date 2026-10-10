import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type Progression, useProgression } from "./api";
import "./gamification.css";

export type Boost = NonNullable<Progression["boost"]>;

/** Seconds until ``iso``, refreshed every half minute (0 once past). */
function useSecondsLeft(iso: string | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!iso) return;
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, [iso]);
  return iso ? Math.max(0, (new Date(iso).getTime() - now) / 1000) : 0;
}

const factorOf = (value: number) => Number(value.toFixed(2));
const factor = (value: number) => `×${factorOf(value)}`;

export function useMyStreak() {
  return useQuery({
    queryKey: ["gamification", "my-streak"],
    queryFn: async () => (await api.GET("/api/v1/me/streak")).data as components["schemas"]["MyStreakOut"],
    staleTime: 60_000,
  });
}

/**
 * #55: the member's boost in progress — its factor and when it ends (the boosts queued after it included).
 * Shown wherever the level is: the header, the progression widgets and page, the shop. Nothing once over.
 */
export function BoostTag({
  boost,
  variant = "chip",
}: {
  boost: Boost | null | undefined;
  /** ``chip``: factor and time left; ``mini``: the factor only (header on a phone, compact widget) */
  variant?: "chip" | "mini";
}) {
  const t = useT();
  const format = useFormat();
  const left = useSecondsLeft(boost?.until);
  if (!boost || left <= 0) return null;
  const gains = boost.gains.map((value) => t(`gamification:value.${value}`)).join(", ");
  const label = t("gamification:boost.active", {
    factor: factorOf(boost.factor),
    gains,
    when: format.relative(left),
  });
  return (
    <Link to="/progression" className="boost-tag" data-variant={variant} title={label} aria-label={label}>
      <Icon name="rocket" size={13} />
      <strong>{factor(boost.factor)}</strong>
      {variant === "chip" ? <small>{format.relative(left)}</small> : null}
    </Link>
  );
}

/** #54/#55: the play streak and the boost in progress, as two small chips — beside what the member earns
 * (daily objectives…), so they know their gains are multiplied. Nothing when neither is on. */
export function GainsNow({ mini = false }: { mini?: boolean }) {
  const t = useT();
  const format = useFormat();
  const streak = useMyStreak().data;
  const boost = useProgression().data?.boost;
  const streaking = streak?.enabled && streak.days > 0;
  if (!streaking && !boost) return null;
  return (
    <span className="gains-now">
      {streaking && streak ? (
        <span
          className="gains-now__streak"
          title={t("gamification:widget.progress.streak", { days: streak.days })}
        >
          <Icon name="flame" size={13} />
          {format.number(streak.days)}
          {streak.multiplier > 1 ? <strong>{factor(streak.multiplier)}</strong> : null}
          {!mini && streak.freezes ? (
            <span title={t("gamification:freeze.owned", { count: streak.freezes })}>
              <Icon name="snowflake" size={12} />
              {format.number(streak.freezes)}
            </span>
          ) : null}
        </span>
      ) : null}
      <BoostTag boost={boost} variant={mini ? "mini" : "chip"} />
    </span>
  );
}
