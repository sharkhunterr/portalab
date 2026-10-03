import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { SelectField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import {
  LEADERBOARD_PERIODS,
  Leaderboard,
  type LeaderboardPeriod,
} from "../../gamification/leaderboards/Leaderboard";

/**
 * ``/community/leaderboards`` (spec 012 T018): 013's leaderboards as the viewer may see them — metric and
 * period selectors, own rank highlighted; ``unavailable`` when 013 is down, without breaking the page.
 */
export function LeaderboardPage() {
  const t = useT();
  const format = useFormat();
  const metrics = useQuery({
    queryKey: ["community", "leaderboards"],
    queryFn: async () => ((await api.GET("/api/v1/community/leaderboards")).data ?? []) as string[],
  });
  const [metric, setMetric] = useState("xp");
  const [period, setPeriod] = useState<LeaderboardPeriod>("all");
  const available = metrics.data ?? [];
  const current = available.includes(metric) ? metric : (available[0] ?? metric);
  const effectivePeriod = current === "level" ? "all" : period;
  const board = useQuery({
    queryKey: ["community", "leaderboard", current, effectivePeriod],
    enabled: available.length > 0,
    queryFn: async () =>
      (
        await api.GET("/api/v1/community/leaderboards/{metric}", {
          params: { path: { metric: current }, query: { period: effectivePeriod } },
        })
      ).data,
  });
  const heading = t("community:leaderboards.title");
  return (
    <section aria-labelledby="community-leaderboards" className="ds-stack">
      <h2 id="community-leaderboards">{heading}</h2>
      {metrics.isSuccess && available.length === 0 ? (
        <FunctionalState state="unavailable" label={t("community:leaderboards.unavailable")} />
      ) : null}
      {available.length ? (
        <div className="ds-stack--row community-filters">
          <SelectField
            label={t("community:leaderboards.metric")}
            value={current}
            onChange={(e) => setMetric(e.target.value)}
          >
            {available.map((value) => (
              <option key={value} value={value}>
                {t(`community:leaderboards.metric.${value}`)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label={t("community:leaderboards.period")}
            value={effectivePeriod}
            disabled={current === "level"}
            onChange={(e) => setPeriod(e.target.value as LeaderboardPeriod)}
          >
            {LEADERBOARD_PERIODS.map((value) => (
              <option key={value} value={value}>
                {t(`community:leaderboards.period.${value}`)}
              </option>
            ))}
          </SelectField>
        </div>
      ) : null}
      {board.isError || board.data?.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("community:leaderboards.unavailable")} />
      ) : null}
      {board.data && board.data.state !== "unavailable" ? (
        <>
          <Leaderboard
            caption={`${heading} — ${t(`community:leaderboards.metric.${current}`)}`}
            rows={board.data.entries}
            me={board.data.me}
            profileLinks
          />
          {board.data.computed_at ? (
            <p className="community-meta">
              {t("community:leaderboards.asOf", { date: format.dateTime(board.data.computed_at) })}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
