/**
 * #68: a page left open across a deployment asks for code files of the previous build, which no longer
 * exist — instead of an « Error » it cannot recover from, it reloads once to get the current build. At
 * most once every 30 seconds, so a real failure never loops.
 */
const KEY = "portalab:stale-build-reload";
const PATTERN =
  /dynamically imported module|Importing a module script failed|error loading dynamically imported|Failed to fetch module|ChunkLoadError|Unable to preload CSS/i;

export function isStaleBuildError(error: unknown): boolean {
  const message = error instanceof Error ? `${error.name} ${error.message}` : String(error ?? "");
  return PATTERN.test(message);
}

/** Reload to the current build; ``false`` when it was just tried (the error is real: show it). */
export function reloadForNewBuild(): boolean {
  try {
    const last = Number(sessionStorage.getItem(KEY) ?? 0);
    if (Date.now() - last < 30_000) return false;
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    // no storage: still reload once (the page cannot remember, the 30 s guard is lost)
  }
  window.location.reload();
  return true;
}

export function watchStaleBuild(): void {
  window.addEventListener("vite:preloadError", (event) => {
    if (reloadForNewBuild()) event.preventDefault();
  });
}
