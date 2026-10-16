import type { ExternalElement } from "./registry";

/**
 * issue 1: a pack's script runs in a sandbox — an iframe of the page ``/api/v1/visuals/sandbox`` with
 * ``sandbox="allow-scripts"`` only: an opaque origin (no cookie, no session, no storage of Portalab's), no
 * network (its own content security policy), no form, no popup, no navigation of this page. It knows only what
 * it is handed here: its module's code (fetched by the interface, the member's session never leaves it), the
 * moment's context, and the files of its own element it asks for (their bytes, never an address).
 *
 * Its messages are recognised by the window they come from, never by their origin (it has none); a navigation
 * may only ask to open one of the pages it was given — the interface checks the key and opens the page itself.
 */

export const SANDBOX_URL = "/api/v1/visuals/sandbox";
/** 028: once ready, the script is asked every few seconds whether it still answers; after a few silences it
 * is stopped (its default takes over) and reported to the administrators. */
export const PING_MS = 2000;
export const MISSES = 3;
const REPORTED = new Set<string>();

/** Tells the administrators an element failed in this page (once per element and page load). */
export function reportFailure(element: ExternalElement, reason: "timeout" | "error" | "unresponsive"): void {
  const key = `${element.pack}:${element.sha}:${element.product}`;
  if (REPORTED.has(key) || typeof fetch === "undefined") return;
  REPORTED.add(key);
  const csrf =
    typeof document === "undefined"
      ? ""
      : (document.cookie
          .split("; ")
          .find((c) => c.startsWith("__Host-portalab_csrf="))
          ?.split("=")[1] ?? "");
  void fetch("/api/v1/visuals/reports", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf) },
    body: JSON.stringify({ pack: element.pack, sha: element.sha, element: element.product, reason }),
  }).catch(() => undefined);
}

export interface SandboxHandlers {
  onReady?: () => void;
  onError?: (message: string) => void;
  onNavigate?: (key: string) => void;
  onExpand?: (open: boolean) => void;
}

export interface Sandbox {
  /** what the script knows changed (a navigation: another page, other counts) */
  update: (context: Record<string, unknown>) => void;
  stop: () => void;
}

const sources = new Map<string, Promise<string | null>>();

/** A module's code, fetched once per address (its version's folder is its fingerprint). */
function moduleSource(url: string): Promise<string | null> {
  let known = sources.get(url);
  if (!known) {
    known = fetch(url, { credentials: "same-origin" })
      .then((response) => (response.ok ? response.text() : null))
      .catch(() => null);
    sources.set(url, known);
  }
  return known;
}

/** A path inside the element's own folder (never up, never absolute, never another site). */
export function safeAssetPath(path: unknown): string | null {
  if (typeof path !== "string" || !path || path.length > 200) return null;
  const clean = path.replace(/^\.\//, "");
  if (clean.startsWith("/") || clean.includes("\\") || clean.includes("\0")) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(clean)) return null;
  if (clean.split("/").some((part) => part === ".." || part === "")) return null;
  return clean;
}

/** Runs ``element``'s script in ``frame`` (an iframe the caller placed); returns how to update and stop it. */
export function runSandbox(
  frame: HTMLIFrameElement,
  element: ExternalElement,
  context: Record<string, unknown>,
  handlers: SandboxHandlers = {},
): Sandbox {
  let stopped = false;
  let started = false;
  let lastNavigation = 0;
  let pinged = 0;
  let answered = 0;
  let heartbeat: ReturnType<typeof setInterval> | null = null;
  const fail = (reason: "error" | "unresponsive", message: string) => {
    if (stopped) return;
    reportFailure(element, reason);
    handlers.onError?.(message);
  };
  const base = element.file ? element.file.slice(0, element.file.lastIndexOf("/") + 1) : "";
  const post = (message: Record<string, unknown>, transfer: Transferable[] = []) => {
    // an opaque origin cannot be named: the message goes to this frame's window only
    frame.contentWindow?.postMessage(message, "*", transfer);
  };
  const listener = async (event: MessageEvent) => {
    if (stopped || event.source !== frame.contentWindow) return;
    const data = event.data as Record<string, unknown> | null;
    if (!data || typeof data !== "object" || typeof data.type !== "string") return;
    switch (data.type) {
      case "loaded": {
        if (started || !element.file) return;
        started = true;
        const source = await moduleSource(element.file);
        if (stopped) return;
        if (source === null) {
          handlers.onError?.("the module could not be loaded");
          return;
        }
        post({ type: "run", source, context, element: { type: element.type, look: element.look } });
        return;
      }
      case "ready":
        handlers.onReady?.();
        if (!heartbeat) {
          heartbeat = setInterval(() => {
            if (pinged - answered >= MISSES) {
              if (heartbeat) clearInterval(heartbeat);
              fail("unresponsive", "the script stopped answering");
              return;
            }
            pinged += 1;
            post({ type: "ping", n: pinged });
          }, PING_MS);
        }
        return;
      case "pong":
        answered = Math.max(answered, Number(data.n) || 0);
        return;
      case "error":
        fail("error", String(data.message ?? "error").slice(0, 300));
        return;
      case "asset": {
        const path = safeAssetPath(data.path);
        if (!path || !base) {
          post({ type: "asset", id: data.id, error: "refused" });
          return;
        }
        try {
          const response = await fetch(base + path, { credentials: "same-origin" });
          if (!response.ok) throw new Error(String(response.status));
          const buffer = await response.arrayBuffer();
          if (stopped) return;
          post({ type: "asset", id: data.id, buffer, mime: response.headers.get("content-type") ?? "" }, [
            buffer,
          ]);
        } catch {
          post({ type: "asset", id: data.id, error: "not found" });
        }
        return;
      }
      case "navigate": {
        // at most a few a second: a script cannot drag the member from page to page
        const now = Date.now();
        if (now - lastNavigation < 400 || typeof data.key !== "string") return;
        lastNavigation = now;
        handlers.onNavigate?.(data.key.slice(0, 120));
        return;
      }
      case "expand":
        handlers.onExpand?.(Boolean(data.open));
        return;
      default:
        return;
    }
  };
  window.addEventListener("message", listener);
  frame.setAttribute("sandbox", "allow-scripts");
  frame.setAttribute("referrerpolicy", "no-referrer");
  frame.src = SANDBOX_URL;
  return {
    update: (next) => {
      if (!stopped && started) post({ type: "context", context: next });
    },
    stop: () => {
      stopped = true;
      if (heartbeat) clearInterval(heartbeat);
      window.removeEventListener("message", listener);
      frame.removeAttribute("src");
    },
  };
}
