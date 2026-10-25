import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { NAVIGATION_KEY } from "../../../shell/nav/NavigationProvider";

/**
 * Issue 246 — the portal's features, as an administrator thinks of them (the wiki, the news, the newsletters,
 * tickets, incidents…), each one the modules it needs and, when it is a part of a module, its switch (a
 * boolean setting). Chosen in the arrival wizard before the first account exists, then in the setup
 * assistant: switching one off disables its modules (dependents first) or its switch; nothing written is
 * deleted, and switching it on again brings it back (a module enabled again after being disabled may need a
 * restart, which is said).
 */
export type FeatureGroup = "media" | "content" | "help" | "play" | "system";

export interface Feature {
  key: string;
  group: FeatureGroup;
  icon: string;
  modules: readonly string[];
  setting?: string;
  needs?: readonly string[]; // other features it cannot go without
}

export const FEATURES: readonly Feature[] = [
  { key: "media", group: "media", icon: "film", modules: ["media"] },
  { key: "wiki", group: "content", icon: "book", modules: ["wiki"] },
  { key: "news", group: "content", icon: "newspaper", modules: ["news"] },
  {
    key: "newsletter",
    group: "content",
    icon: "mail",
    modules: ["news"],
    setting: "news.newsletter.enabled",
    needs: ["news"],
  },
  { key: "calendar", group: "content", icon: "calendar", modules: ["calendar"] },
  {
    key: "tickets",
    group: "help",
    icon: "lifebuoy",
    modules: ["support"],
    setting: "support.tickets.enabled",
  },
  {
    key: "incidents",
    group: "help",
    icon: "alert",
    modules: ["support"],
    setting: "support.incidents.enabled",
  },
  { key: "status", group: "help", icon: "activity", modules: ["health"] },
  { key: "ai", group: "help", icon: "bot", modules: ["ai"] },
  { key: "play", group: "play", icon: "trophy", modules: ["gamification", "campaigns", "community"] },
  { key: "shop", group: "play", icon: "store", modules: ["marketplace"], needs: ["play"] },
  { key: "automations", group: "system", icon: "zap", modules: ["automations"] },
  { key: "statistics", group: "system", icon: "chart", modules: ["statistics"] },
  { key: "dashboard", group: "system", icon: "dashboard", modules: ["dashboard"] },
  { key: "search", group: "system", icon: "search", modules: ["search"] },
];

export const GROUPS: readonly FeatureGroup[] = ["media", "content", "help", "play", "system"];

export type Selection = ReadonlySet<string>;

/** Every feature on: a new portal's choice before the administrator says otherwise. */
export const ALL_FEATURES: Selection = new Set(FEATURES.map((f) => f.key));

/** One feature switched on or off: what it needs comes on with it, what needs it goes with it. */
export function toggle(selection: Selection, key: string, on: boolean): Set<string> {
  const next = new Set(selection);
  const visit = (k: string, value: boolean) => {
    if (value === next.has(k)) return;
    if (value) {
      next.add(k);
      for (const need of FEATURES.find((f) => f.key === k)?.needs ?? []) visit(need, true);
    } else {
      next.delete(k);
      for (const f of FEATURES) if (f.needs?.includes(k)) visit(f.key, false);
    }
  };
  visit(key, on);
  return next;
}

export interface ModuleState {
  key: string;
  enabled: boolean;
  requires: string[];
  essential: boolean;
  needs_restart: boolean;
}

export interface SettingValue {
  key: string;
  value: unknown;
}

/** The features on today, read from the modules and the switches. */
export function selectionOf(modules: readonly ModuleState[], settings: readonly SettingValue[]): Set<string> {
  const enabled = new Set(modules.filter((m) => m.enabled).map((m) => m.key));
  const known = new Set(modules.map((m) => m.key));
  const on = new Set<string>();
  for (const f of FEATURES) {
    const modulesOn = f.modules.every((m) => enabled.has(m) || !known.has(m));
    const switchOn = !f.setting || settings.find((s) => s.key === f.setting)?.value !== false;
    if (modulesOn && switchOn) on.add(f.key);
  }
  return on;
}

export interface Plan {
  enable: string[]; // dependencies first
  disable: string[]; // dependents first
  settings: Array<{ key: string; value: boolean }>;
}

/** What the selection changes: the modules to enable or disable (in an order their dependencies accept) and
 * the switches to set. A module no feature manages (the kernel, content, events…) is never disabled. */
export function planFor(selection: Selection, modules: readonly ModuleState[]): Plan {
  const byKey = new Map(modules.map((m) => [m.key, m]));
  const managed = new Set(FEATURES.flatMap((f) => f.modules));
  const wanted = new Set<string>();
  const want = (key: string) => {
    if (wanted.has(key) || !byKey.has(key)) return;
    wanted.add(key);
    for (const dep of byKey.get(key)?.requires ?? []) want(dep);
  };
  for (const f of FEATURES) if (selection.has(f.key)) for (const m of f.modules) want(m);
  const depth = (key: string, seen = new Set<string>()): number => {
    if (seen.has(key)) return 0;
    seen.add(key);
    const deps = byKey.get(key)?.requires ?? [];
    return deps.length ? 1 + Math.max(...deps.map((d) => depth(d, seen))) : 0;
  };
  const enable = [...wanted]
    .filter((k) => !byKey.get(k)?.enabled)
    .sort((a, b) => depth(a) - depth(b) || a.localeCompare(b));
  const disable = [...managed]
    .filter((k) => !wanted.has(k) && byKey.get(k)?.enabled && !byKey.get(k)?.essential)
    .sort((a, b) => depth(b) - depth(a) || a.localeCompare(b));
  const settings = FEATURES.filter((f) => f.setting).map((f) => ({
    key: f.setting as string,
    value: selection.has(f.key),
  }));
  return { enable, disable, settings };
}

async function readModules(): Promise<ModuleState[]> {
  return ((await api.GET("/api/v1/admin/modules")).data ?? []) as unknown as ModuleState[];
}

/** Where applying a selection is (issue 249: the arrival wizard's progress): ``done`` of ``total`` changes,
 * the module being changed (``null`` for the switches). */
export type ApplyProgress = (done: number, total: number, module: string | null) => void;

/** Applies a selection on the portal (as its administrator): the switches, then the modules. Answers whether
 * a module must wait for a restart to come back. */
export async function applySelection(
  selection: Selection,
  onProgress: ApplyProgress = () => undefined,
): Promise<{ restart: boolean }> {
  const plan = planFor(selection, await readModules());
  const total = 1 + plan.disable.length + plan.enable.length;
  let done = 0;
  onProgress(done, total, null);
  await api.PUT("/api/v1/admin/config", {
    body: {
      changes: plan.settings.map((s) => ({ ...s, scope: "global", scope_ref: "", unset: false })),
      reason: "features",
    } as never,
  });
  for (const [key, enabled] of [
    ...plan.disable.map((k) => [k, false] as const),
    ...plan.enable.map((k) => [k, true] as const),
  ]) {
    onProgress(++done, total, key);
    await api.PUT("/api/v1/admin/modules", { body: { key, enabled, cascade: false } as never });
  }
  onProgress(total, total, null);
  return { restart: (await readModules()).some((m) => m.needs_restart) };
}

/** A selection being chosen and applied, from the portal's current state (once signed in). */
export function useFeatureDraft(initial: Selection = ALL_FEATURES) {
  const client = useQueryClient();
  const [selection, setSelection] = useState<Selection>(initial);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [restart, setRestart] = useState(false);
  const set = (key: string, on: boolean) => {
    setSelection((current) => toggle(current, key, on));
    setState("idle");
  };
  const apply = async () => {
    setState("saving");
    try {
      const result = await applySelection(selection);
      setRestart(result.restart);
      setState("saved");
      await client.invalidateQueries({ queryKey: ["admin", "config"] });
      await client.invalidateQueries({ queryKey: ["plugins", "modules"] });
      await client.invalidateQueries({ queryKey: NAVIGATION_KEY });
      return true;
    } catch {
      setState("error");
      return false;
    }
  };
  return { selection, setSelection, set, apply, state, restart };
}
