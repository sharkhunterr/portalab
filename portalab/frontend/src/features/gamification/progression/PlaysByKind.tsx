import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { AdminTabs } from "../../../design-system/admin/AdminKit";
import { BarsChart } from "../../../design-system/charts/Charts";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { SOURCES } from "./GainSources";

type Plays = components["schemas"]["PlaysOut"];
const PERIODS = [7, 30, 90, 365];

export function usePlays(days: number, admin: boolean, member = "") {
  return useQuery({
    queryKey: ["gamification", "plays", admin, days, member],
    queryFn: async () =>
      (admin
        ? (
            await api.GET("/api/v1/admin/gamification/plays", {
              params: { query: { days, ...(member ? { member } : {}) } },
            })
          ).data
        : (await api.GET("/api/v1/me/progression/plays", { params: { query: { days } } })).data) as Plays,
  });
}

/** « 2 h 05 », « 45 min » — the time a kind of play took. */
export function useDuration() {
  const t = useT();
  return (seconds: number) => {
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return t("gamification:plays.minutes", { count: minutes });
    return t("gamification:plays.hours", {
      hours: Math.floor(minutes / 60),
      minutes: String(minutes % 60).padStart(2, "0"),
    });
  };
}

function KindName({ play }: { play: string }) {
  const t = useT();
  return (
    <span className="plays__kind">
      <span
        className="gain-sources__dot"
        style={{ background: SOURCES[play]?.color ?? "var(--cal-other)" }}
        aria-hidden="true"
      >
        <Icon name={SOURCES[play]?.icon ?? "play"} size={12} />
      </span>
      {t(`gamification:sources.${play}`)}
    </span>
  );
}

/**
 * Issue 160 — plays by kind: episodes, films, live TV, books, audiobooks, music… each with its sittings, the
 * works finished, the time it took, the XP and Coins it earned (bonuses included) — and, for the
 * administrators, how many members; the sittings day by day as stacked bars. A table first (it reads on a
 * phone), the chart beside it.
 */
export function PlaysByKind({
  admin = false,
  member = "",
  days: fixedDays,
}: {
  admin?: boolean;
  member?: string;
  /** the administration's period, set by its overview (the member page picks its own) */
  days?: number;
}) {
  const t = useT();
  const format = useFormat();
  const duration = useDuration();
  const headingId = useId();
  const [ownDays, setDays] = useState(30);
  const days = fixedDays ?? ownDays;
  const [chart, setChart] = useState(true);
  const data = usePlays(days, admin, member).data;
  const kinds = data?.kinds ?? [];
  const keys = kinds.map((k) => k.play);
  const bars = (data?.days ?? []).map((d) => ({ day: d.day.slice(5), ...d.sittings }));
  const sum = (field: "sittings" | "finished" | "watched_s" | "xp" | "coins") =>
    kinds.reduce((total, k) => total + k[field], 0);
  return (
    <section className="ds-card plays" aria-labelledby={headingId}>
      <header className="gain-sources__head">
        <h2 id={headingId}>
          <Icon name="play" size={20} />{" "}
          {t(admin ? "gamification:plays.adminTitle" : "gamification:plays.title")}
        </h2>
        {fixedDays === undefined ? (
          <div className="gain-sources__filters">
            <AdminTabs
              label={t("gamification:sources.period")}
              current={String(days)}
              onChange={(next) => setDays(Number(next))}
              tabs={PERIODS.map((p) => ({
                key: String(p),
                label: t("gamification:admin.overview.days", { days: p }),
              }))}
            />
          </div>
        ) : null}
      </header>
      {data && !kinds.length ? <p className="admin-muted">{t("gamification:plays.empty")}</p> : null}
      {kinds.length ? (
        <div className="plays__body">
          <div className="plays__table">
            <table
              className="plays__grid"
              aria-label={t(admin ? "gamification:plays.adminTitle" : "gamification:plays.title")}
            >
              <thead>
                <tr>
                  <th scope="col">{t("gamification:plays.kind")}</th>
                  <th scope="col" data-align="end">
                    {t("gamification:plays.sittings")}
                  </th>
                  <th scope="col" data-align="end">
                    {t("gamification:plays.finished")}
                  </th>
                  <th scope="col" data-align="end">
                    {t("gamification:plays.time")}
                  </th>
                  <th scope="col" data-align="end">
                    {t("gamification:value.xp")}
                  </th>
                  <th scope="col" data-align="end">
                    {t("gamification:value.coins")}
                  </th>
                  {admin ? (
                    <th scope="col" data-align="end">
                      {t("gamification:plays.members")}
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {kinds.map((k) => (
                  <tr key={k.play}>
                    <th scope="row">
                      <KindName play={k.play} />
                    </th>
                    <td data-align="end">{format.number(k.sittings)}</td>
                    <td data-align="end">{format.number(k.finished)}</td>
                    <td data-align="end">{duration(k.watched_s)}</td>
                    <td data-align="end">
                      <strong>{format.number(k.xp)}</strong>
                    </td>
                    <td data-align="end">{format.number(k.coins)}</td>
                    {admin ? <td data-align="end">{format.number(k.members)}</td> : null}
                  </tr>
                ))}
              </tbody>
              {kinds.length > 1 ? (
                <tfoot>
                  <tr>
                    <th scope="row">{t("gamification:plays.total")}</th>
                    <td data-align="end">{format.number(sum("sittings"))}</td>
                    <td data-align="end">{format.number(sum("finished"))}</td>
                    <td data-align="end">{duration(sum("watched_s"))}</td>
                    <td data-align="end">
                      <strong>{format.number(sum("xp"))}</strong>
                    </td>
                    <td data-align="end">{format.number(sum("coins"))}</td>
                    {admin ? <td /> : null}
                  </tr>
                </tfoot>
              ) : null}
            </table>
          </div>
          {chart ? (
            <figure className="plays__chart">
              <figcaption>{t("gamification:plays.daily")}</figcaption>
              <div aria-hidden="true">
                <BarsChart
                  data={bars}
                  x="day"
                  stacked
                  height={220}
                  legend={false}
                  format={(value) => format.number(value)}
                  series={keys.map((key) => ({
                    key,
                    label: t(`gamification:sources.${key}`),
                    color: SOURCES[key]?.color ?? "var(--cal-other)",
                  }))}
                />
              </div>
            </figure>
          ) : null}
        </div>
      ) : null}
      {kinds.length ? (
        <Button variant="ghost" onClick={() => setChart(!chart)} aria-expanded={chart}>
          <Icon name="chart" size={16} />
          {chart ? t("gamification:plays.hideChart") : t("gamification:plays.showChart")}
        </Button>
      ) : null}
    </section>
  );
}
