import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type PointerEvent, useEffect, useId, useRef, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { AdminSection, FormActions, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLevelCurve } from "../api";
import { VALUES } from "./tuning";

type Pace = Required<components["schemas"]["PaceConfig"]>;
type Population = components["schemas"]["PopulationOut"];

const W = 640;
const H = 300;
const PAD = { left: 40, right: 16, top: 16, bottom: 32 };
const DAYS = 365;
const FALLBACK_RATE = 50; // XP a day, when nobody earned anything yet
const MARKS = [30, 90, 180, 365];

/** Continuous level for an XP total (inverse of ``base · (n - 1)^exponent``). */
function levelAt(xp: number, base: number, exponent: number): number {
  return xp <= 0 ? 1 : 1 + (xp / base) ** (1 / exponent);
}

function xpFor(level: number, base: number, exponent: number): number {
  return level <= 1 ? 0 : base * (level - 1) ** exponent;
}

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

/**
 * Progression tuning (027, the « simple » setting): instead of the XP of each action, the administrator
 * shapes **how fast members progress**. The chart shows where members stand (days since their first XP,
 * level), the pace of active members (median, and the most active fifth) projected over a year, and the
 * projection with the pace being set. Dragging the curve — or the slider — sets one factor applied to the
 * gains of every rule (« pace »); the XP of each action is left as it is.
 */
export function ProgressionTuner() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const sliderId = useId();
  const svg = useRef<SVGSVGElement>(null);
  const curve = useLevelCurve();
  const pace = useQuery({
    queryKey: ["gamification", "admin", "pace"],
    queryFn: async () => (await api.GET("/api/v1/admin/gamification/pace")).data as Pace,
  });
  const population = useQuery({
    queryKey: ["gamification", "admin", "population"],
    queryFn: async () => (await api.GET("/api/v1/admin/gamification/population")).data as Population,
  });
  const save = useMutation({
    mutationFn: async (body: Pace) =>
      (await api.PUT("/api/v1/admin/gamification/pace", { body })).data as Pace,
    onSuccess: (data) => {
      client.setQueryData(["gamification", "admin", "pace"], data);
      setSaved(true);
    },
  });
  const [factor, setFactor] = useState(1);
  const [values, setValues] = useState<string[]>(["xp"]);
  const [saved, setSaved] = useState(false);
  const [dragging, setDragging] = useState(false);
  useEffect(() => {
    if (pace.data) {
      setFactor(pace.data.factor);
      setValues(pace.data.values);
    }
  }, [pace.data]);
  if (!curve.data || !pace.data || !population.data) {
    return pace.isError || population.isError ? (
      <FunctionalState state="unavailable" onRetry={() => void population.refetch()} />
    ) : (
      <FunctionalState state="loading" />
    );
  }
  const { base, exponent } = curve.data.definition;
  const current = pace.data.factor || 1;
  // observed paces were earned with the current factor: bring them back to the rules' own pace
  const measured = population.data.rate_median > 0;
  const rate = (measured ? population.data.rate_median : FALLBACK_RATE) / current;
  const rateHigh = (population.data.rate_high > 0 ? population.data.rate_high : rate * current * 2) / current;
  const members = population.data.members;
  const project = (f: number, r: number, day: number) => levelAt(f * r * day, base, exponent);
  // the scale follows the typical member (set and current) and where members stand; the most active
  // fifth may run off the top — it is clipped rather than flattening everything else
  const levels = members.map((m) => m.level).sort((a, b) => a - b);
  const p90 = levels[Math.floor(levels.length * 0.9)] ?? 1;
  const top = Math.ceil(Math.max(10, project(factor, rate, DAYS), project(current, rate, DAYS), p90) * 1.25);
  const x = (day: number) => PAD.left + (day / DAYS) * (W - PAD.left - PAD.right);
  const y = (level: number) => H - PAD.bottom - ((level - 1) / (top - 1)) * (H - PAD.top - PAD.bottom);
  const path = (f: number, r: number) =>
    Array.from({ length: 74 }, (_, i) => i * 5)
      .map((day, i) => `${i ? "L" : "M"}${x(day).toFixed(1)},${y(project(f, r, day)).toFixed(1)}`)
      .join(" ");
  const change = (next: number) => {
    setSaved(false);
    setFactor(Math.round(clamp(next, 0.1, 10) * 100) / 100);
  };
  // dragging: the projected curve passes through the pointer → the factor follows
  const follow = (event: PointerEvent<SVGSVGElement>) => {
    const box = svg.current?.getBoundingClientRect();
    if (!box) return;
    const px = ((event.clientX - box.left) / box.width) * W;
    const py = ((event.clientY - box.top) / box.height) * H;
    const day = clamp(((px - PAD.left) / (W - PAD.left - PAD.right)) * DAYS, 14, DAYS);
    const level = clamp(1 + ((H - PAD.bottom - py) / (H - PAD.top - PAD.bottom)) * (top - 1), 1.05, top);
    change(xpFor(level, base, exponent) / (rate * day));
  };
  const handleDay = DAYS;
  const ticks = Array.from({ length: 5 }, (_, i) => Math.round(1 + (i * (top - 1)) / 4));
  return (
    <AdminSection
      span="full"
      icon="trending"
      title={t("gamification:admin.pace.title")}
      description={t("gamification:admin.pace.hint")}
      actions={
        <StatusBadge tone={Math.abs(factor - current) < 0.005 ? "neutral" : "info"}>×{factor}</StatusBadge>
      }
    >
      <div className="gam-pace">
        <figure className="gam-pace__chart">
          <svg
            ref={svg}
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={t("gamification:admin.pace.chart")}
            data-dragging={dragging || undefined}
            onPointerDown={(event) => {
              event.currentTarget.setPointerCapture(event.pointerId);
              setDragging(true);
              follow(event);
            }}
            onPointerMove={(event) => {
              if (dragging) follow(event);
            }}
            onPointerUp={() => setDragging(false)}
            onPointerCancel={() => setDragging(false)}
          >
            <defs>
              <clipPath id={`${sliderId}-plot`}>
                <rect
                  x={PAD.left}
                  y={PAD.top}
                  width={W - PAD.left - PAD.right}
                  height={H - PAD.top - PAD.bottom}
                />
              </clipPath>
            </defs>
            {ticks.map((level) => (
              <g key={level}>
                <line
                  x1={PAD.left}
                  x2={W - PAD.right}
                  y1={y(level)}
                  y2={y(level)}
                  className="gam-pace__grid"
                />
                <text x={PAD.left - 6} y={y(level) + 4} textAnchor="end" className="gam-pace__tick">
                  {level}
                </text>
              </g>
            ))}
            {MARKS.map((day) => (
              <g key={day}>
                <line x1={x(day)} x2={x(day)} y1={PAD.top} y2={H - PAD.bottom} className="gam-pace__grid" />
                <text x={x(day)} y={H - 10} textAnchor="middle" className="gam-pace__tick">
                  {t("gamification:admin.pace.months", { months: Math.round(day / 30) })}
                </text>
              </g>
            ))}
            <g clipPath={`url(#${sliderId}-plot)`}>
              {members.map((member) => (
                <circle
                  key={member.user_id}
                  cx={x(Math.min(member.days, DAYS))}
                  cy={y(member.level)}
                  r={4}
                  className="gam-pace__member"
                >
                  <title>
                    {member.name ?? member.user_id.slice(0, 8)} ·{" "}
                    {t("gamification:level", { level: member.level })}
                  </title>
                </circle>
              ))}
              <path d={path(current, rate)} className="gam-pace__line" data-kind="current" />
              <path d={path(factor, rateHigh)} className="gam-pace__line" data-kind="high" />
              <path d={path(factor, rate)} className="gam-pace__line" data-kind="draft" />
            </g>
            <circle
              cx={x(handleDay)}
              cy={y(project(factor, rate, handleDay))}
              r={9}
              className="gam-pace__handle"
            />
          </svg>
          <figcaption className="gam-pace__legend">
            <span data-kind="member">
              {t("gamification:admin.pace.legend.members", { count: members.length })}
            </span>
            <span data-kind="current">{t("gamification:admin.pace.legend.current")}</span>
            <span data-kind="draft">{t("gamification:admin.pace.legend.draft")}</span>
            <span data-kind="high">{t("gamification:admin.pace.legend.high")}</span>
          </figcaption>
        </figure>
        <div className="gam-pace__side">
          <label htmlFor={sliderId} className="gam-pace__label">
            {t("gamification:admin.pace.factor")} <strong>×{factor}</strong>
          </label>
          <input
            id={sliderId}
            type="range"
            min={0.1}
            max={5}
            step={0.05}
            value={factor}
            aria-valuetext={`×${factor}`}
            onChange={(e) => change(Number(e.target.value))}
          />
          <dl className="gam-milestones">
            {MARKS.map((day) => (
              <div key={day}>
                <dt>{t("gamification:admin.pace.after", { months: Math.round(day / 30) })}</dt>
                <dd>{t("gamification:level", { level: Math.floor(project(factor, rate, day)) })}</dd>
              </div>
            ))}
          </dl>
          <p className="admin-muted">
            {measured
              ? t("gamification:admin.pace.measured", {
                  rate: format.number(Math.round(rate * factor)),
                  active: population.data.active,
                })
              : t("gamification:admin.pace.estimated", { rate: FALLBACK_RATE })}
          </p>
          <fieldset className="gam-fieldset">
            <legend>{t("gamification:admin.pace.values")}</legend>
            <div className="gam-checks">
              {VALUES.map((value) => (
                <CheckboxField
                  key={value}
                  label={t(`gamification:value.${value}`)}
                  checked={values.includes(value)}
                  onChange={(e) => {
                    setSaved(false);
                    setValues(e.target.checked ? [...values, value] : values.filter((v) => v !== value));
                  }}
                />
              ))}
            </div>
          </fieldset>
          {saved ? <p role="status">{t("gamification:admin.saved")}</p> : null}
          {save.isError ? (
            <p role="alert" className="services-admin__ko">
              {t("gamification:admin.saveFailed")}
            </p>
          ) : null}
          <FormActions>
            <Button variant="ghost" onClick={() => change(1)}>
              {t("gamification:admin.pace.reset")}
            </Button>
            <Button disabled={save.isPending} onClick={() => save.mutate({ factor, values })}>
              <Icon name="check" size={16} />
              {t("gamification:admin.save")}
            </Button>
          </FormActions>
        </div>
      </div>
    </AdminSection>
  );
}
