import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useShellPreference } from "../../shell/preferences";
import { completeStep, completeTour, MISSIONS_KEY, TOUR_EVENT } from "./api";
import { type TourDef, type TourStep, tourOf } from "./tours";
import "./onboarding.css";

/**
 * The guided tours (#7): a light circles one element at a time over the real pages and a bubble says what
 * it is for (the steps of each tour are in ``tours.ts``). It opens the pages it needs, follows whatever the
 * theme put where and leaves out what is not shown; « Next » does a step's action when it has one. Arrows
 * move, Escape leaves; on a phone the bubble sits at the bottom (or the top) of the screen. Seeing a tour
 * to its end is said once (``/me/onboarding/tours/<tour>/complete``) — some first steps are just that.
 */
function shown(element: Element): boolean {
  const rect = element.getBoundingClientRect();
  if (rect.width < 4 || rect.height < 4) return false;
  const style = window.getComputedStyle(element);
  return style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity) > 0.05;
}

export function findTarget(step: TourStep): HTMLElement | null {
  for (const selector of step.targets) {
    let found: Element[] = [];
    try {
      found = Array.from(document.querySelectorAll(selector));
    } catch {
      continue; // a selector the browser does not know
    }
    const element = found.find((candidate) => !candidate.closest(".tour") && shown(candidate));
    if (element) return element as HTMLElement;
  }
  return null;
}

interface Box {
  top: number;
  left: number;
  width: number;
  height: number;
}

const PAD = 8;
const GAP = 14;
/** How long a step waits for its element (a page loading, a panel opening) before it is left out. */
export const TOUR_TIMING = { patience: 2500 };

/** The veil with a hole where the light is (rounded; the hole lets clicks through to the element). */
function veil(spot: Box | null): string | undefined {
  if (!spot) return undefined;
  const w = window.innerWidth;
  const h = window.innerHeight;
  const r = Math.min(14, spot.width / 2, spot.height / 2);
  const { top: y, left: x, width: sw, height: sh } = spot;
  return `path(evenodd, "M0 0H${w}V${h}H0Z M${x + r} ${y}H${x + sw - r}A${r} ${r} 0 0 1 ${x + sw} ${y + r}V${y + sh - r}A${r} ${r} 0 0 1 ${x + sw - r} ${y + sh}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + sh - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z")`;
}

function clip(rect: DOMRect): Box {
  const top = Math.max(rect.top - PAD, 4);
  const left = Math.max(rect.left - PAD, 4);
  const bottom = Math.min(rect.bottom + PAD, window.innerHeight - 4);
  const right = Math.min(rect.right + PAD, window.innerWidth - 4);
  return { top, left, width: Math.max(right - left, 0), height: Math.max(bottom - top, 0) };
}

/** Where the bubble goes: beside the light where it fits, docked to the screen's edge on a phone. */
function place(spot: Box | null, bubble: { width: number; height: number }): Record<string, number | string> {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (!spot)
    return { top: Math.max((vh - bubble.height) / 2, 16), left: Math.max((vw - bubble.width) / 2, 16) };
  if (vw < 640) {
    const lower = spot.top + spot.height / 2 > vh / 2;
    return lower ? { top: 16, left: 16, right: 16 } : { bottom: 16, left: 16, right: 16 };
  }
  const centreX = Math.min(
    Math.max(spot.left + spot.width / 2 - bubble.width / 2, 16),
    vw - bubble.width - 16,
  );
  const centreY = Math.min(
    Math.max(spot.top + spot.height / 2 - bubble.height / 2, 16),
    vh - bubble.height - 16,
  );
  if (vh - (spot.top + spot.height) >= bubble.height + GAP + 16)
    return { top: spot.top + spot.height + GAP, left: centreX };
  if (spot.top >= bubble.height + GAP + 16) return { top: spot.top - bubble.height - GAP, left: centreX };
  if (vw - (spot.left + spot.width) >= bubble.width + GAP + 16)
    return { top: centreY, left: spot.left + spot.width + GAP };
  if (spot.left >= bubble.width + GAP + 16) return { top: centreY, left: spot.left - bubble.width - GAP };
  return { bottom: 16, left: centreX };
}

export function Tour() {
  const [running, setRunning] = useState<TourDef | null>(null);
  const [run, setRun] = useState(0);
  useEffect(() => {
    const start = (event: Event) => {
      const tour = tourOf((event as CustomEvent<string | undefined>).detail ?? "portal");
      if (!tour) return;
      setRunning(tour);
      setRun((n) => n + 1);
    };
    window.addEventListener(TOUR_EVENT, start);
    return () => window.removeEventListener(TOUR_EVENT, start);
  }, []);
  if (!running) return null;
  return createPortal(<TourRun key={run} tour={running} onClose={() => setRunning(null)} />, document.body);
}

function TourRun({ tour, onClose }: { tour: TourDef; onClose: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const titleId = useId();
  const textId = useId();
  const [seen, setSeen] = useShellPreference<string[]>("shell.onboarding.toursSeen", []);
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const [ready, setReady] = useState(false); // the step's element was found (or it has none)
  const [spot, setSpot] = useState<Box | null>(null);
  const [position, setPosition] = useState<Record<string, number | string>>({});
  const bubble = useRef<HTMLDivElement>(null);
  const primary = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<Element | null>(document.activeElement);
  const steps = tour.steps;
  const step = steps[index] as TourStep;
  const last = index === steps.length - 1;
  const pathname = useRef(location.pathname);
  pathname.current = location.pathname;

  // open the page the step needs, then wait for its element; one that never shows is left out
  useEffect(() => {
    setReady(false);
    setTarget(null);
    const route = step.route ?? (index === 0 ? tour.route : undefined);
    if (route && pathname.current !== route) navigate(route);
    if (!step.targets.length) {
      setReady(true);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      const found = findTarget(step);
      if (found) {
        window.clearInterval(timer);
        setTarget(found);
        setReady(true);
      } else if (Date.now() - started > (route ? 3 : 1) * TOUR_TIMING.patience) {
        // a step that opens a page waits longer: the page loads first (issue 181: the shop's shelves)
        window.clearInterval(timer);
        setIndex((i) => Math.min(Math.max(i + direction, 0), steps.length - 1));
      }
    }, 120);
    return () => window.clearInterval(timer);
  }, [step, index, direction, tour.route, navigate, steps.length]);

  const measure = useCallback(() => {
    const element = target?.isConnected ? target : step.targets.length ? findTarget(step) : null;
    const box = element ? clip(element.getBoundingClientRect()) : null;
    setSpot(box);
    const size = bubble.current?.getBoundingClientRect() ?? { width: 340, height: 180 };
    setPosition(place(box, { width: size.width, height: size.height }));
  }, [step, target]);

  // bring the element into view, then follow it (scrolling, resizing, late layout)
  useLayoutEffect(() => {
    if (!ready) return;
    if (target) {
      const rect = target.getBoundingClientRect();
      if (rect.top < 0 || rect.bottom > window.innerHeight)
        target.scrollIntoView({ block: rect.height > window.innerHeight ? "start" : "center" });
    }
    measure();
    primary.current?.focus({ preventScroll: true });
    const timer = window.setInterval(measure, 300);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [ready, target, measure]);

  const leave = useCallback(() => {
    onClose();
    if (previousFocus.current instanceof HTMLElement && previousFocus.current.isConnected)
      previousFocus.current.focus({ preventScroll: true });
  }, [onClose]);

  const finish = useCallback(() => {
    if (!seen.includes(tour.key)) setSeen([...seen, tour.key]);
    const said =
      tour.key === "portal"
        ? completeStep("tour").then(() => completeTour("portal"))
        : completeTour(tour.key);
    // issue 121: the mission is completed by the worker a moment later — asked again once it had the time
    const refresh = () => void client.invalidateQueries({ queryKey: MISSIONS_KEY });
    void said
      .then(() => {
        refresh();
        window.setTimeout(refresh, 4000);
      })
      .catch(() => undefined);
    onClose();
  }, [client, onClose, seen, setSeen, tour.key]);

  const next = useCallback(() => {
    if (last) {
      finish();
      return;
    }
    if (step.click && target?.isConnected) target.click(); // the step's action, done for the member
    setDirection(1);
    setIndex((i) => i + 1);
  }, [last, finish, step.click, target]);
  const back = useCallback(() => {
    setDirection(-1);
    setIndex((i) => Math.max(i - 1, 0));
  }, []);

  // a step with an action goes on when the member does it themselves
  useEffect(() => {
    if (!step.click || !target) return;
    const onClick = (event: MouseEvent) => {
      if (event.isTrusted && event.target instanceof Node && target.contains(event.target)) {
        setDirection(1);
        setIndex((i) => Math.min(i + 1, steps.length - 1));
      }
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [step.click, target, steps.length]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        leave();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        next();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        back();
      } else if (event.key === "Tab") {
        // the focus stays in the bubble while the tour runs
        const focusable = bubble.current?.querySelectorAll<HTMLElement>("button:not([disabled])");
        if (!focusable?.length) return;
        const first = focusable[0] as HTMLElement;
        const end = focusable[focusable.length - 1] as HTMLElement;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          end.focus();
        } else if (!event.shiftKey && document.activeElement === end) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [leave, next, back]);

  const text = (field: "title" | "text") => t(`onboarding:tours.${tour.key}.${step.key}.${field}`);
  return (
    <div className="tour" data-ready={ready ? "true" : undefined}>
      <div
        className="tour__scrim"
        aria-hidden="true"
        style={spot && ready ? { clipPath: veil(spot) } : undefined}
      />
      <div
        className="tour__spot"
        aria-hidden="true"
        data-empty={spot && ready ? undefined : "true"}
        style={
          spot && ready
            ? { top: spot.top, left: spot.left, width: spot.width, height: spot.height }
            : { top: "50%", left: "50%", width: 0, height: 0 }
        }
      />
      {ready ? (
        <div
          ref={bubble}
          key={`${tour.key}-${step.key}`}
          className="tour__bubble"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={textId}
          data-docked={window.innerWidth < 640 && spot ? "true" : undefined}
          style={position}
        >
          <div className="tour__head">
            <span className="tour__icon" aria-hidden="true">
              <Icon name={step.icon} size={20} />
            </span>
            <p className="tour__count">
              {t(`onboarding:tours.${tour.key}.title`)} · {index + 1}/{steps.length}
            </p>
            <button
              type="button"
              className="tour__close"
              onClick={leave}
              aria-label={t("onboarding:tour.leave")}
            >
              <Icon name="close" size={16} />
            </button>
          </div>
          <h2 id={titleId} className="tour__title">
            {text("title")}
          </h2>
          <p id={textId} className="tour__text">
            {text("text")}
          </p>
          <div className="tour__progress" aria-hidden="true">
            <span style={{ width: `${((index + 1) / steps.length) * 100}%` }} />
          </div>
          <div className="tour__actions">
            {index > 0 ? (
              <Button variant="ghost" onClick={back}>
                {t("onboarding:back")}
              </Button>
            ) : (
              <Button variant="ghost" onClick={leave}>
                {t("onboarding:skip")}
              </Button>
            )}
            <Button ref={primary} onClick={next}>
              {last
                ? t("onboarding:tour.finish")
                : step.click
                  ? t("onboarding:tour.doIt")
                  : t("onboarding:next")}
              {last ? null : <Icon name="chevron-right" size={18} />}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
