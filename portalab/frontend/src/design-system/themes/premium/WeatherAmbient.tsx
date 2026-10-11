import { type ReactNode, useEffect, useState } from "react";

/**
 * #68: « live weather » — the ambience follows the sky over the homelab: a storm, a downpour, a blizzard,
 * fog, a clear day in the forest or a clear night of stars. The weather comes from the server (refreshed
 * every 15 minutes); until a place is set, a starry sky.
 */
interface Sky {
  condition: string | null;
  is_day: boolean;
}

export function weatherAmbient(sky: Sky | null): string {
  switch (sky?.condition) {
    case "storm":
      return "thunderstorm";
    case "rain":
      return "downpour";
    case "snow":
      return "blizzard";
    case "fog":
    case "cloudy":
      return "fog";
    case "clear":
      return sky.is_day ? "forest" : "cosmos";
    default:
      return "starfield";
  }
}

export function WeatherAmbient({ render }: { render: (kind: string) => ReactNode }) {
  const [sky, setSky] = useState<Sky | null>(null);
  useEffect(() => {
    let alive = true;
    const ask = async () => {
      try {
        const response = await fetch("/api/v1/ui/weather", { credentials: "same-origin" });
        if (response.ok && alive) setSky((await response.json()) as Sky);
      } catch {
        // no weather: the starry sky stays
      }
    };
    void ask();
    const timer = window.setInterval(ask, 15 * 60 * 1000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);
  return <>{render(weatherAmbient(sky))}</>;
}
