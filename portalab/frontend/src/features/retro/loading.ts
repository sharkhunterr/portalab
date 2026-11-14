import { useEffect, useState } from "react";

/** Issue 420: what the play page shows while the game loads — a step after another, with its progress. */
export type StepKey = "sitting" | "emulator" | "core" | "bios" | "game" | "state" | "start";
export type Action = "download" | "decompress" | "load";

export interface Loading {
  key: StepKey;
  action: Action;
  percent: number | null; // null: no size known (megabytes only)
  megabytes: number | null;
}

/** EmulatorJS's own words for its steps (English; read through its translation when it has one). */
const PHRASES: ReadonlyArray<[StepKey, Action, string]> = [
  ["core", "download", "Download Game Core"],
  ["core", "decompress", "Decompress Game Core"],
  ["core", "decompress", "Decompress Game Assets"],
  ["bios", "download", "Download Game BIOS"],
  ["bios", "decompress", "Decompress Game BIOS"],
  ["game", "download", "Download Game Parent"],
  ["game", "decompress", "Decompress Game Parent"],
  ["game", "download", "Download Game Patch"],
  ["game", "decompress", "Decompress Game Patch"],
  ["game", "download", "Download Game Data"],
  ["game", "decompress", "Decompress Game Data"],
  ["state", "download", "Download Game State"],
];

/** What EmulatorJS is doing, from the line it shows (« Download Game Core 45% », « … 1.20MB »). */
export function readLoading(text: string, localize: (phrase: string) => string = (p) => p): Loading | null {
  const line = text.trim();
  if (!line) return null;
  for (const [key, action, phrase] of PHRASES) {
    const words = [localize(phrase), phrase];
    if (words.some((w) => w && line.startsWith(w))) {
      const percent = /(\d{1,3})\s*%/.exec(line);
      const size = /([\d.]+)\s*MB/i.exec(line);
      return {
        key,
        action,
        percent: percent ? Math.min(100, Number(percent[1])) : null,
        megabytes: size ? Number(size[1]) : null,
      };
    }
  }
  return { key: "emulator", action: "load", percent: null, megabytes: null }; // « Loading… »
}

type EjsLike = { localization?: (phrase: string) => string };

/** The step EmulatorJS is at, and its error once it fails, read from its own screen while ``running``. */
export function useEmulatorLoading(running: boolean): { loading: Loading | null; error: string | null } {
  const [loading, setLoading] = useState<Loading | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!running) return;
    const root = document.getElementById("retro-game");
    if (!root) return;
    const read = () => {
      const failed = root.querySelector(".ejs_error_text");
      if (failed?.textContent?.trim()) {
        setError(failed.textContent.trim());
        return;
      }
      const line = root.querySelector(".ejs_loading_text")?.textContent ?? "";
      const ejs = (window as unknown as { EJS_emulator?: EjsLike }).EJS_emulator;
      const localize = (phrase: string) => {
        try {
          return ejs?.localization?.(phrase) ?? phrase;
        } catch {
          return phrase;
        }
      };
      const found = readLoading(line, localize);
      if (found) setLoading(found);
    };
    const watcher = new MutationObserver(read);
    watcher.observe(root, { subtree: true, childList: true, characterData: true, attributes: true });
    read();
    return () => watcher.disconnect();
  }, [running]);
  return { loading, error };
}
