import { useEffect, useState } from "react";
import { resolvePalette, suggest } from "../../../features/search/api";
import { useT } from "../../../i18n/hooks/useT";
import type { Command } from "../CommandRegistry";

/**
 * Palette search provider (spec 008 T030): for the typed text, asks the server in parallel for
 * (1) the palette resolution — object reference, deterministic intent, permitted context actions and
 * assistant *suggestions* — and (2) inline search results. Each source fails on its own; the local
 * commands always stay. Suggestions are labelled and never executed without the user's choice.
 */
export function useSearchCommands(query: string, route: string, enabled: boolean): Command[] {
  const t = useT();
  const [commands, setCommands] = useState<Command[]>([]);
  useEffect(() => {
    const text = query.trim();
    if (!enabled) {
      setCommands([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      const [resolution, results] = await Promise.all([
        resolvePalette(text, route).catch(() => null),
        text ? suggest(text).catch(() => []) : Promise.resolve([]),
      ]);
      if (cancelled) return;
      const out: Command[] = [];
      if (resolution?.object) {
        const { kind, id, title, route: objectRoute } = resolution.object;
        out.push({
          id: `object:${kind}:${id}`,
          label: t("search:palette.open", { title }),
          keywords: [],
          route: objectRoute,
        });
      }
      const intent = resolution?.intent;
      if (intent?.type === "navigate" || intent?.type === "command") {
        const entry = [...(resolution?.destinations ?? []), ...(resolution?.actions ?? [])].find(
          (e) => e.id === intent.target,
        );
        if (entry && intent.route)
          out.push({
            id: `intent:${entry.id}`,
            label: entry.label,
            keywords: [],
            route: intent.route,
            sensitive: entry.confirmation_required,
          });
      }
      for (const action of resolution?.actions ?? []) {
        if (!action.route || out.some((c) => c.id === `intent:${action.id}`)) continue;
        out.push({
          id: `action:${action.id}`,
          label: action.label,
          keywords: action.keywords,
          route: action.route,
          sensitive: action.confirmation_required,
        });
      }
      for (const item of results) {
        out.push({
          id: `result:${item.kind}:${item.id}`,
          label: item.title,
          keywords: [item.kind],
          route: item.url_ref,
        });
      }
      if (text) {
        const q = intent?.type === "search" && intent.query ? intent.query : text;
        out.push({
          id: "search:page",
          label: t("search:palette.searchFor", { query: q }),
          keywords: [],
          route: `/search?q=${encodeURIComponent(q)}`,
        });
      }
      for (const suggestion of resolution?.suggestions ?? []) {
        if (!suggestion.route) continue;
        out.push({
          id: `suggested:${suggestion.route}`,
          label: `${suggestion.label} · ${t("search:palette.suggested")}`,
          keywords: [],
          route: suggestion.route,
        });
      }
      setCommands(out);
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, route, enabled, t]);
  return commands;
}
