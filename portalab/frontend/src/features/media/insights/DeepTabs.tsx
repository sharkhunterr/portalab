import { useState } from "react";
import { AdminEmpty, AdminGrid, AdminSection } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useRequestInsights } from "../requests/api";
import { Overview as RequestsOverview } from "../requests/RequestsPage";
import { type Category, type Scope, useInsightSection, useMeasures } from "./api";
import {
  ActivityCompare,
  BreakdownBars,
  ClockWheel,
  CompareBars,
  CountryMap,
  Donut,
  FinanceTiles,
  GenreRadar,
  GenreStack,
  GenreSummary,
  QUALITY_COLORS,
  Registry,
  RoiList,
  STREAM_COLORS,
  WeekWheel,
} from "./DeepCharts";
import "../requests/requests.css";

/**
 * 027 — the statistics' tabs beyond the overview (after Telemetra): Profile (activity against the previous
 * period, genres new / rising / always / gone, radar, genres by period, the viewing footprint), Casting
 * (directors and actors), Production (budgets, financial successes and flops, release years, countries),
 * Playback (direct play or transcoded, resolution, players and platforms) — and my Requests.
 */
interface TabProps {
  scope: Scope;
  category: Category;
  period: string;
}

function Loading({ state, retry }: { state: "pending" | "error" | "success"; retry: () => void }) {
  if (state === "pending") return <FunctionalState state="loading" />;
  if (state === "error") return <FunctionalState state="error" onRetry={retry} />;
  return null;
}

export function ProfileTab({ scope, category, period }: TabProps) {
  const t = useT();
  const query = useInsightSection("profile", scope, category, period);
  const [metric, setMetric] = useState<"plays" | "completed">("plays");
  const data = query.data;
  if (!data) return <Loading state={query.status} retry={() => query.refetch()} />;
  return (
    <AdminGrid>
      <AdminSection
        title={t("media:deep.activity")}
        description={t("media:deep.activityHint")}
        icon="activity"
        span="full"
        actions={
          <fieldset className="insights-toggle">
            <legend className="visually-hidden">{t("media:insights.chartMetric")}</legend>
            {(["plays", "completed"] as const).map((key) => (
              <label key={key} className="insights-toggle__item" data-checked={metric === key || undefined}>
                <input
                  type="radio"
                  name="deep-metric"
                  checked={metric === key}
                  onChange={() => setMetric(key)}
                />
                {t(`media:deep.metric.${key}`)}
              </label>
            ))}
          </fieldset>
        }
      >
        <ActivityCompare data={data} metric={metric} />
      </AdminSection>
      <AdminSection
        title={t("media:deep.genreProfile")}
        description={t("media:deep.genreProfileHint")}
        icon="palette"
        span="full"
      >
        {data.genres.length ? (
          <div className="deep-split">
            <GenreSummary data={data} />
            <GenreRadar data={data} />
          </div>
        ) : (
          <AdminEmpty icon="palette" title={t("media:deep.noGenres")} />
        )}
      </AdminSection>
      <AdminSection
        title={t("media:deep.genresByPeriod")}
        description={t("media:deep.genresByPeriodHint")}
        icon="chart"
        span="full"
      >
        <GenreStack data={data} />
      </AdminSection>
      <AdminSection
        title={t("media:deep.footprint")}
        description={t("media:deep.footprintHint")}
        icon="clock"
        span="full"
      >
        <div className="deep-wheels">
          <ClockWheel hours={data.hours} />
          <WeekWheel weekdays={data.weekdays} />
        </div>
      </AdminSection>
    </AdminGrid>
  );
}

export function CastingTab({ scope, category, period }: TabProps) {
  const t = useT();
  const query = useInsightSection("casting", scope, category, period);
  const data = query.data;
  if (!data) return <Loading state={query.status} retry={() => query.refetch()} />;
  const unit = category === "series" ? "media:deep.seriesCount" : "media:deep.filmsCount";
  return (
    <AdminGrid>
      <AdminSection
        title={t(category === "series" ? "media:deep.creators" : "media:deep.directors")}
        description={t("media:deep.registryHint")}
        icon="clapperboard"
      >
        <Registry title={t("media:deep.registryDirectors")} people={data.directors.slice(0, 5)} unit={unit} />
      </AdminSection>
      <AdminSection title={t("media:deep.actors")} description={t("media:deep.registryHint")} icon="drama">
        <Registry title={t("media:deep.registryCast")} people={data.actors.slice(0, 5)} unit={unit} />
      </AdminSection>
    </AdminGrid>
  );
}

export function ProductionTab({ scope, category, period }: TabProps) {
  const t = useT();
  const measures = useMeasures();
  const query = useInsightSection("production", scope, category, period);
  const data = query.data;
  if (!data) return <Loading state={query.status} retry={() => query.refetch()} />;
  if (!data.films) return <AdminEmpty icon="coins" title={t("media:deep.noMetadata")} />;
  const movies = Boolean(data.budgets);
  return (
    <AdminGrid>
      {movies ? (
        <AdminSection
          title={t("media:deep.finance.title")}
          description={t("media:deep.finance.hint")}
          icon="coins"
          span="full"
        >
          <FinanceTiles data={data} />
        </AdminSection>
      ) : null}
      {data.budgets ? (
        <AdminSection
          title={t("media:deep.byBudget")}
          description={
            data.budget_average
              ? t("media:deep.byBudgetHint", { value: measures.money(data.budget_average) })
              : undefined
          }
          icon="chart"
          span="full"
        >
          <CompareBars
            rows={data.budgets.map((b) => ({ key: b.range, count: b.count, previous: b.previous }))}
            hasPrevious={data.has_previous}
            label={(key) => t(`media:deep.range.${key}`)}
          />
        </AdminSection>
      ) : null}
      {data.successes ? (
        <AdminSection
          title={t("media:deep.successes")}
          description={t("media:deep.successesHint")}
          icon="trending"
          span="full"
        >
          <RoiList films={data.successes} tone="ok" />
        </AdminSection>
      ) : null}
      {data.flops ? (
        <AdminSection
          title={t("media:deep.flops")}
          description={t("media:deep.flopsHint")}
          icon="arrow-down"
          span="full"
        >
          <RoiList films={data.flops} tone="bad" />
        </AdminSection>
      ) : null}
      <AdminSection
        title={t("media:deep.years")}
        description={
          data.year_average ? t("media:deep.yearsHint", { year: Math.round(data.year_average) }) : undefined
        }
        icon="calendar"
        span="full"
      >
        <CompareBars
          rows={data.years.map((y) => ({ key: String(y.year), count: y.count, previous: y.previous }))}
          hasPrevious={data.has_previous}
          averages={{ now: data.year_average, before: data.year_average_previous }}
        />
      </AdminSection>
      <AdminSection
        title={t("media:deep.countries")}
        description={t("media:deep.countriesHint")}
        icon="globe"
        span="full"
      >
        <CountryMap countries={data.countries} />
      </AdminSection>
    </AdminGrid>
  );
}

export function PlaybackTab({ scope, category, period }: TabProps) {
  const t = useT();
  const format = useFormat();
  const query = useInsightSection("playback", scope, category, period);
  const data = query.data;
  if (!data) return <Loading state={query.status} retry={() => query.refetch()} />;
  if (!data.total) return <AdminEmpty icon="play" title={t("media:insights.none")} />;
  const stream = (key: string) => t(`media:deep.stream.${key}`);
  const quality = (key: string) => t(`media:deep.quality.${key}`);
  const known = data.streams.totals.some((s) => s.key !== "unknown");
  return (
    <AdminGrid>
      <AdminSection
        title={t("media:deep.streams")}
        description={t("media:deep.streamsHint")}
        icon="zap"
        span="full"
      >
        {known ? (
          <BreakdownBars
            data={data.streams}
            buckets={data.buckets}
            unit={data.unit}
            hasPrevious={data.has_previous}
            colors={STREAM_COLORS}
            label={stream}
          />
        ) : (
          <AdminEmpty icon="zap" title={t("media:deep.noStream")} />
        )}
      </AdminSection>
      <AdminSection title={t("media:deep.streamShare")} icon="gauge" span="full">
        <div className="deep-pair">
          <div>
            <p className="deep-pair__title">{t("media:deep.current")}</p>
            <Donut
              slices={data.streams.totals.map((s) => ({ key: s.key, value: s.count }))}
              total={data.total}
              caption={t("media:deep.playsWord")}
              colors={(key) => STREAM_COLORS[key] ?? "var(--chart-other)"}
              label={stream}
            />
          </div>
          {data.has_previous ? (
            <div data-previous="">
              <p className="deep-pair__title">{t("media:deep.previous")}</p>
              <Donut
                slices={data.streams.totals.map((s) => ({ key: s.key, value: s.previous }))}
                total={data.total_previous}
                caption={t("media:deep.playsWord")}
                colors={() => "var(--chart-previous)"}
                label={stream}
              />
            </div>
          ) : null}
        </div>
        {data.total ? (
          <p className="admin-muted deep-note">
            <Icon name="check" size={14} />
            {t("media:deep.directShare", {
              value: format.percent(
                (data.streams.totals.find((s) => s.key === "direct")?.count ?? 0) / data.total,
              ),
            })}
          </p>
        ) : null}
      </AdminSection>
      <AdminSection
        title={t("media:deep.qualities")}
        description={t("media:deep.qualitiesHint")}
        icon="tv"
        span="full"
      >
        {data.qualities.totals.some((q) => q.key !== "unknown") ? (
          <BreakdownBars
            data={data.qualities}
            buckets={data.buckets}
            unit={data.unit}
            hasPrevious={data.has_previous}
            colors={QUALITY_COLORS}
            label={quality}
          />
        ) : (
          <AdminEmpty icon="tv" title={t("media:deep.noStream")} />
        )}
      </AdminSection>
      <AdminSection
        title={t("media:deep.support")}
        description={t("media:deep.supportHint")}
        icon="smartphone"
        span="full"
      >
        <div className="deep-pair">
          {data.devices ? (
            <div>
              <p className="deep-pair__title">{t("media:deep.players")}</p>
              <Donut
                slices={data.devices.map((d) => ({ key: d.name, value: d.count }))}
                total={data.devices.reduce((a, d) => a + d.count, 0)}
                caption={t("media:deep.players")}
                colors={(_key, i) => `var(--chart-${(i % 8) + 1})`}
                label={(key) => key}
              />
            </div>
          ) : null}
          <div>
            <p className="deep-pair__title">{t("media:deep.platforms")}</p>
            <Donut
              slices={data.platforms.map((d) => ({ key: d.name, value: d.count }))}
              total={data.platforms.reduce((a, d) => a + d.count, 0)}
              caption={t("media:deep.platforms")}
              colors={(_key, i) => `var(--chart-${(i % 8) + 1})`}
              label={(key) => key}
            />
          </div>
        </div>
      </AdminSection>
    </AdminGrid>
  );
}

export function RequestsTab({ period }: { period: string }) {
  const query = useRequestInsights(period);
  if (!query.data) return <Loading state={query.status} retry={() => query.refetch()} />;
  return <RequestsOverview data={query.data} />;
}
