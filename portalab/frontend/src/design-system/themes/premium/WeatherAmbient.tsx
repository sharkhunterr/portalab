import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { PremiumAmbient } from "./PremiumAmbient";
import { fallbackOf, type Scene, sceneOf, type WeatherReport } from "./weatherScene";

/**
 * #68, #70, #88: « live weather » — the ambience draws the sky over the member's place (their own, or the
 * portal's default) as the forecast tells it: the hour's light, the clouds, what falls and how hard, the fog,
 * the lightning, the wind, the frost, the moon in its phase (``weatherScene.ts`` → ``weatherShader.ts``). The
 * report comes from the server (refreshed every 15 minutes, and at once when the member picks another place);
 * a change of weather blends in over a few seconds. Until a place is set, a clear sky of the hour.
 */

/** Sent when the member picks another place: the ambience asks for its sky again. */
export const WEATHER_PLACE_CHANGED = "portalab:weather-place";

export function useWeatherReport(enabled = true): WeatherReport | null {
  const [report, setReport] = useState<WeatherReport | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const ask = async () => {
      try {
        const response = await fetch("/api/v1/ui/weather", { credentials: "same-origin" });
        if (response.ok && alive) setReport((await response.json()) as WeatherReport);
      } catch {
        // no weather: the sky stays as it was
      }
    };
    void ask();
    const timer = window.setInterval(ask, 15 * 60 * 1000);
    const again = () => void ask();
    window.addEventListener(WEATHER_PLACE_CHANGED, again);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener(WEATHER_PLACE_CHANGED, again);
    };
  }, [enabled]);
  return report;
}

/** Whether the page under the ambience is light (white clouds and snow are then drawn a little darker). */
function usePaper() {
  const paper = useRef(0);
  useEffect(() => {
    const read = () => {
      const [r = 0, g = 0, b = 0] = (
        getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g) ?? []
      ).map(Number);
      paper.current = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.6 ? 1 : 0;
    };
    read();
    // a theme or a colour scheme changed: read the page again
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "style", "data-theme"],
    });
    return () => observer.disconnect();
  }, []);
  return paper;
}

const SETTLE_MS = 1200; // a new sky settles in about three seconds, however fast the device draws

export function WeatherAmbient({
  contained = false,
  fallback,
  report: shown,
}: {
  contained?: boolean;
  /** the CSS ambience drawn instead when the device cannot (``rain``, ``snow``, ``fog``…) */
  fallback: (kind: string) => ReactNode;
  /** a given sky (a preview of each weather) instead of the one outside */
  report?: WeatherReport | null | undefined;
}) {
  const live = useWeatherReport(shown === undefined);
  const report = shown === undefined ? live : shown;
  const target = useRef<Scene>(sceneOf(report));
  const current = useRef<Scene>({ ...target.current });
  target.current = sceneOf(report);
  const last = useRef(0);
  const paper = usePaper();
  const uniforms = useCallback(() => {
    const now = current.current as unknown as Record<string, number>;
    const goal = target.current as unknown as Record<string, number>;
    const at = performance.now();
    const step = last.current ? 1 - Math.exp(-(at - last.current) / SETTLE_MS) : 1;
    last.current = at;
    for (const key of Object.keys(goal)) {
      const to = goal[key] as number;
      const from = now[key] ?? to;
      // the wind's side and the dawn/dusk hue turn at once; everything else blends
      now[key] =
        key === "windDir" || key === "dawn" || Math.abs(to - from) < 0.002 ? to : from + (to - from) * step;
    }
    now.paper = paper.current;
    return now;
  }, [paper]);
  return (
    <PremiumAmbient
      kind="weathersky"
      contained={contained}
      uniforms={uniforms}
      fallback={fallback(fallbackOf(report))}
    />
  );
}
