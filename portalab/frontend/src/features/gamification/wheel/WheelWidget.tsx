import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { CurrencyShort } from "../../../design-system/site/SiteLook";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { holdGains } from "../../../shell/header/useHeaderData";
import type { WidgetPayload } from "../../dashboard/api";
import { WidgetStage } from "../../dashboard/widgets/pack/WidgetAddons";
import { registerWidgetComponent, type WidgetProps } from "../../dashboard/widgets/registry";
import "./wheel.css";

export interface WheelSegment {
  key: string;
  kind: "coins" | "xp" | "product" | "nothing";
  amount: number;
  product?: string | null;
  label?: string | null;
}

export interface WheelSpin {
  segment: string;
  index: number | null;
  kind: string;
  amount: number;
  delta: number;
  product?: string | null;
  given: boolean;
  spun_at: string;
}

export interface WheelState {
  enabled: boolean;
  day: string;
  next_at: string;
  spin_ms: number;
  coins: number;
  segments: WheelSegment[];
  today: WheelSpin | null;
}

type Phase = "idle" | "spinning" | "done";

const TURNS = 6;
const EASING = "cubic-bezier(0.12, 0.8, 0.18, 1)";

/** A segment's tone: what a look colours it by (won, lost, XP, a gift, nothing). */
export function toneOf(segment: WheelSegment): string {
  if (segment.kind === "coins") return segment.amount < 0 ? "lose" : "coins";
  return segment.kind;
}

/** Where the wheel rests with segment ``index`` under the pointer (at the top), in degrees. */
export function restingAngle(index: number, count: number): number {
  const slice = 360 / count;
  return (360 - (index * slice + slice / 2)) % 360;
}

/** The angle a spin ends on: whole turns past ``from``, then segment ``index`` under the pointer, a little
 * off its middle (never on an edge). */
export function landingAngle(from: number, index: number, count: number, jitter = 0): number {
  const slice = 360 / count;
  const base = Math.ceil(from / 360) * 360 + TURNS * 360;
  return base + restingAngle(index, count) + Math.max(-0.35, Math.min(0.35, jitter)) * slice;
}

function slicePath(index: number, count: number): string {
  const slice = (Math.PI * 2) / count;
  const start = index * slice - Math.PI / 2;
  const end = start + slice;
  const point = (a: number) => `${50 + 50 * Math.cos(a)} ${50 + 50 * Math.sin(a)}`;
  return `M50 50 L${point(start)} A50 50 0 ${slice > Math.PI ? 1 : 0} 1 ${point(end)} Z`;
}

/** Portalab's own face (when no pack draws one): a slice per segment, coloured by its tone. */
function WheelFace({ segments }: { segments: WheelSegment[] }) {
  return (
    <svg className="wheel__face" viewBox="0 0 100 100" aria-hidden="true">
      {segments.map((segment, index) => (
        <path
          key={segment.key}
          className="wheel__slice"
          d={slicePath(index, segments.length)}
          data-tone={toneOf(segment)}
          data-odd={index % 2 === 1 || undefined}
        />
      ))}
    </svg>
  );
}

/** What each segment gives — always written by Portalab, over any face a pack draws. */
function WheelLabels({ segments }: { segments: WheelSegment[] }) {
  const t = useT();
  const slice = 360 / segments.length;
  return (
    <div className="wheel__labels" aria-hidden="true">
      {segments.map((segment, index) => (
        <span
          key={segment.key}
          className="wheel__label"
          data-tone={toneOf(segment)}
          style={{ "--wheel-at": `${index * slice + slice / 2}deg` } as CSSProperties}
        >
          {segment.kind === "product" ? (
            <Icon name="gift" size={14} />
          ) : segment.kind === "nothing" ? (
            <Icon name="minus" size={13} />
          ) : (
            <>
              <span>
                {segment.amount > 0 ? "+" : "−"}
                {Math.abs(segment.amount)}
              </span>
              {segment.kind === "xp" ? <small>{t("gamification:wheel.xp")}</small> : null}
            </>
          )}
        </span>
      ))}
    </div>
  );
}

function Bulbs() {
  return (
    <span className="wheel__bulbs" aria-hidden="true">
      {Array.from({ length: 16 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: fixed decorative bulbs around the rim
        <span key={i} style={{ "--wheel-at": `${i * 22.5}deg` } as CSSProperties} />
      ))}
    </span>
  );
}

/** What the spin gave, in words (written once the wheel stopped). */
function Outcome({ spin, segment }: { spin: WheelSpin; segment: WheelSegment | undefined }) {
  const t = useT();
  const format = useFormat();
  if (spin.kind === "product") {
    const name = segment?.label ?? spin.product ?? "";
    return spin.given ? (
      <p className="wheel__outcome" data-tone="product">
        <Icon name="gift" size={18} />
        <span>
          {t("gamification:wheel.won.product", { name })}{" "}
          <Link to="/marketplace/reserve">{t("gamification:wheel.reserve")}</Link>
        </span>
      </p>
    ) : (
      <p className="wheel__outcome" data-tone="coins">
        <Icon name="coins" size={18} />
        <span>{t("gamification:wheel.won.fallback", { name, amount: format.number(spin.delta) })}</span>
      </p>
    );
  }
  if (spin.kind === "nothing") {
    return (
      <p className="wheel__outcome" data-tone="nothing">
        <Icon name="cloud" size={18} />
        <span>{t("gamification:wheel.won.nothing")}</span>
      </p>
    );
  }
  if (spin.kind === "xp") {
    return (
      <p className="wheel__outcome" data-tone="xp">
        <Icon name="sparkles" size={18} />
        <span>{t("gamification:wheel.won.xp", { amount: format.number(spin.delta) })}</span>
      </p>
    );
  }
  if (spin.amount < 0) {
    return (
      <p className="wheel__outcome" data-tone="lose">
        <Icon name="thumbs-down" size={18} />
        <span>
          {spin.delta < 0
            ? t("gamification:wheel.won.lose", { amount: format.number(-spin.delta) })
            : t("gamification:wheel.won.spared", { amount: format.number(-spin.amount) })}
        </span>
      </p>
    );
  }
  return (
    <p className="wheel__outcome" data-tone="coins">
      <Icon name="coins" size={18} />
      <span>
        {t("gamification:wheel.won.coins", { amount: format.number(spin.delta) })} <CurrencyShort />
      </span>
    </p>
  );
}

function useCountdown(until: string): string {
  const format = useFormat();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const minutes = Math.max(1, Math.round((new Date(until).getTime() - now) / 60_000));
  return minutes >= 60
    ? `${format.number(Math.floor(minutes / 60))} h ${String(minutes % 60).padStart(2, "0")}`
    : `${format.number(minutes)} min`;
}

/**
 * issue 225: the daily wheel. The server draws (``POST /me/wheel/spin``) and gives before anything turns;
 * this page then turns the wheel to the segment it was told, and writes what it gave once it stopped. A
 * pack's look may paint it (a stylesheet) or draw its face (a script in the region kept for it, turned with
 * the wheel); the amounts, the pointer, the button and the result are always Portalab's.
 */
export function WheelWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const client = useQueryClient();
  const state = payload.data as unknown as WheelState;
  const segments = state.segments;
  const count = Math.max(1, segments.length);
  // the server's answer, kept here too (the widget may not be fed from the dashboard's cache: a preview)
  const [answer, setAnswer] = useState<WheelSpin | null>(null);
  const today = state.today ?? answer;
  const resting = today?.index != null ? restingAngle(today.index, count) : 0;
  const [angle, setAngle] = useState(resting);
  const [phase, setPhase] = useState<Phase>(today ? "done" : "idle");
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const reduced =
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const spinMs = reduced ? 600 : state.spin_ms;
  const countdown = useCountdown(state.next_at);

  const spin = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/me/wheel/spin");
      if (error || !data) throw error ?? new Error("spin");
      return data as unknown as WheelState;
    },
    onSuccess: (next) => {
      setAnswer(next.today);
      const index = next.today?.index ?? 0;
      setAngle((from) => landingAngle(from, index, next.segments.length, Math.random() - 0.5));
      setPhase("spinning");
      // the widget's data now says what was drawn (a pack's face turns with it)
      client.setQueriesData<WidgetPayload>({ queryKey: ["widget", "gamification.daily_wheel"] }, (old) =>
        old ? { ...old, data: next as unknown as Record<string, unknown> } : old,
      );
      timer.current = window.setTimeout(() => {
        setPhase("done");
        release.current?.();
        void client.invalidateQueries({ queryKey: ["gamification"] });
        void client.invalidateQueries({ queryKey: ["marketplace"] });
        void client.invalidateQueries({ queryKey: ["shell", "attention"] }); // a booster in my reserve
      }, spinMs);
    },
    onError: () => {
      release.current?.();
      void client.invalidateQueries({ queryKey: ["widget", "gamification.daily_wheel"] });
    },
  });

  // spun elsewhere (another page, another device): it rests on what it drew
  useEffect(() => {
    if (today && phase === "idle") {
      setAngle(today.index != null ? restingAngle(today.index, count) : 0);
      setPhase("done");
    }
  }, [today, phase, count]);
  const shown: Phase = today && phase === "idle" ? "done" : phase;
  // the header's Coins and the celebration wait until the wheel stopped (they would tell the result first)
  const release = useRef<(() => void) | null>(null);
  const go = () => {
    release.current = holdGains(spinMs + 8000);
    spin.mutate();
  };
  const segment = today ? segments.find((s) => s.key === today.segment) : undefined;
  const canSpin = !today && phase === "idle" && !spin.isPending;
  return (
    <div className="wheel-host">
      <div className="wheel" data-phase={shown} data-compact={compact || undefined}>
        <div className="wheel__stage">
          <Bulbs />
          <div
            className="wheel__spinner"
            style={
              {
                transform: `rotate(${angle}deg)`,
                transition: phase === "spinning" ? `transform ${spinMs}ms ${EASING}` : "none",
              } as CSSProperties
            }
          >
            <WidgetStage
              fallback={<WheelFace segments={segments} />}
              stage={{ phase: shown, spin_ms: spinMs }}
            />
            <WheelLabels segments={segments} />
          </div>
          <span className="wheel__pointer" aria-hidden="true" />
          <button
            type="button"
            className="wheel__hub"
            disabled={!canSpin}
            onClick={go}
            aria-label={t("gamification:wheel.spin")}
          >
            {canSpin ? (
              t("gamification:wheel.go")
            ) : (
              <Icon name={phase === "spinning" ? "spinner" : "check"} size={16} />
            )}
          </button>
        </div>
        <div className="wheel__side" aria-live="polite">
          {shown === "done" && today ? (
            <>
              <Outcome spin={today} segment={segment} />
              <p className="wheel__next">
                <Icon name="clock" size={14} />
                {t("gamification:wheel.next", { time: countdown })}
              </p>
            </>
          ) : shown === "spinning" ? (
            <p className="wheel__status">{t("gamification:wheel.spinning")}</p>
          ) : (
            <>
              <p className="wheel__status">{t("gamification:wheel.ready")}</p>
              {compact ? null : <p className="wheel__hint">{t("gamification:wheel.hint")}</p>}
              <button type="button" className="ds-button wheel__go" disabled={!canSpin} onClick={go}>
                <Icon name="ferris-wheel" size={16} />
                {t("gamification:wheel.spin")}
              </button>
            </>
          )}
          {spin.isError ? <p role="alert">{t("gamification:wheel.failed")}</p> : null}
        </div>
      </div>
    </div>
  );
}

registerWidgetComponent("gamification.daily_wheel", WheelWidget, { stage: true });
