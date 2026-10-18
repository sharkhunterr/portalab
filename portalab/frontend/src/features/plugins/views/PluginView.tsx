import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useIntl } from "react-intl";
import { useNavigate } from "react-router";
import { api } from "../../../api/client";
import { connectStream, type StreamHandle } from "../../../api/stream";
import { useTheme } from "../../../design-system/themes/ThemeProvider";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { ApiError } from "../../../state/regions";
import { ownLink } from "../pages/Blocks";
import { Cancelled, usePluginAction } from "../pages/PluginConfirm";
import { THEME_KIT } from "./kit";

/**
 * 030: a plugin's own view — its page, modal, drawer, panel or launcher drawn by the plugin itself, in the
 * sandbox of spec 028 (a frame of an opaque origin: no session, no cookie, no network, nothing of Portalab's
 * page). It follows the member's theme, interface and palette: Portalab hands it its tokens as CSS variables
 * and a base kit built on them, again whenever they change. It acts only through Portalab: its own plugin's
 * routes as the member (a committing one confirmed in Portalab's own dialog), its own live topics, its own
 * surfaces and pages, a title's page.
 */

export const VIEW_SANDBOX = "/api/v1/plugins/sandbox";
const PATH = /^[a-z0-9_\-/]{1,120}$/;
const NAME = /^[a-z][a-z0-9_]{0,47}$/;
const ASSET = /^[a-z0-9_\-/.]{1,160}$/;
// Portalab's base tokens (a theme sets more on <html>: all of them are handed over)
const BASE_TOKENS = [
  "--color-bg",
  "--color-surface",
  "--color-surface-raised",
  "--color-text",
  "--color-text-muted",
  "--color-border",
  "--color-accent",
  "--color-accent-alt",
  "--color-accent-contrast",
  "--color-focus",
  "--state-error-fg",
  "--state-error-bg",
  "--state-available-fg",
  "--state-partial-fg",
  "--space-1",
  "--space-2",
  "--space-3",
  "--space-4",
  "--space-6",
  "--radius-sm",
  "--radius-md",
  "--radius-lg",
  "--radius-pill",
  "--font-size-xs",
  "--font-size-sm",
  "--font-size-md",
  "--font-size-lg",
  "--font-weight-medium",
  "--font-weight-semibold",
  "--font-weight-bold",
  "--font-sans",
  "--font-display",
  "--font-size-xl",
  "--shadow-sm",
  "--motion-easing",
  "--motion-duration-fast",
  "--motion-duration-normal",
  "--target-min",
];

/** The member's tokens as they are now (the theme's custom properties on ``<html>``, read computed). */
export function currentTokens(root: HTMLElement = document.documentElement): Record<string, string> {
  const names = new Set(BASE_TOKENS);
  for (let index = 0; index < root.style.length; index += 1) {
    const name = root.style.item(index);
    if (name.startsWith("--")) names.add(name);
  }
  const computed = getComputedStyle(root);
  const out: Record<string, string> = {};
  for (const name of names) {
    const value = computed.getPropertyValue(name).trim();
    if (value && value.length <= 200 && !value.includes("url(")) out[name] = value;
  }
  return out;
}

interface FontData {
  family: string;
  buffer: ArrayBuffer;
  descriptors: Record<string, string>;
}

let fontCache: Promise<Array<Omit<FontData, "buffer"> & { url: string }>> | null = null;

/** The @font-face rules of Portalab's interface fonts (``--font-sans``, ``--font-display``), found once. */
function fontFaces(): Promise<Array<Omit<FontData, "buffer"> & { url: string }>> {
  if (fontCache) return fontCache;
  fontCache = (async () => {
    const computed = getComputedStyle(document.documentElement);
    const families = new Set(
      ["--font-sans", "--font-display"]
        .map((token) =>
          computed
            .getPropertyValue(token)
            .split(",")[0]
            ?.trim()
            .replace(/^["']|["']$/g, ""),
        )
        .filter((name): name is string => Boolean(name)),
    );
    if (!families.size) return [];
    const found: Array<Omit<FontData, "buffer"> & { url: string }> = [];
    for (const sheet of Array.from(document.styleSheets)) {
      let rules: CSSRuleList;
      try {
        rules = sheet.cssRules;
      } catch {
        continue;
      }
      for (const rule of Array.from(rules)) {
        if (!(rule instanceof CSSFontFaceRule)) continue;
        const name = rule.style
          .getPropertyValue("font-family")
          .trim()
          .replace(/^["']|["']$/g, "");
        if (!families.has(name)) continue;
        const url = /url\(["']?([^"')]+\.woff2)["']?\)/.exec(rule.style.getPropertyValue("src"))?.[1];
        if (!url || !url.startsWith("/")) continue;
        found.push({
          family: name,
          url,
          descriptors: {
            weight: rule.style.getPropertyValue("font-weight") || "400",
            style: rule.style.getPropertyValue("font-style") || "normal",
            unicodeRange: rule.style.getPropertyValue("unicode-range") || "U+0-10FFFF",
          },
        });
        if (found.length >= 6) return found;
      }
    }
    return found;
  })();
  return fontCache;
}

async function portalFonts(): Promise<FontData[]> {
  const faces = await fontFaces().catch(() => []);
  const out: FontData[] = [];
  for (const face of faces) {
    const response = await fetch(face.url, { credentials: "same-origin" }).catch(() => null);
    if (response?.ok)
      out.push({ family: face.family, descriptors: face.descriptors, buffer: await response.arrayBuffer() });
  }
  return out;
}

export interface PluginViewProps {
  plugin: string;
  view: string;
  params?: Record<string, string>;
  /** ``page``: grows with its content; ``fill``: fills its container; ``launcher``: a fixed small size */
  mode: "page" | "fill" | "launcher";
  title: string;
  size?: { width?: number; height?: number } | null;
  onOpen?: (surface: string, params: Record<string, string>) => void;
  onClose?: () => void;
}

function clean(params: unknown): Record<string, string> {
  if (!params || typeof params !== "object") return {};
  return Object.fromEntries(
    Object.entries(params as Record<string, unknown>)
      .filter(([k]) => /^[a-z][a-z0-9_]{0,31}$/.test(k))
      .slice(0, 12)
      .map(([k, v]) => [k, String(v).slice(0, 200)]),
  );
}

export function PluginView({
  plugin,
  view,
  params = {},
  mode,
  title,
  size,
  onOpen,
  onClose,
}: PluginViewProps) {
  const frame = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(mode === "page" ? 480 : 0);
  const [failed, setFailed] = useState(false);
  const navigate = useNavigate();
  const action = usePluginAction(plugin);
  const intl = useIntl();
  const locale = useLocaleContext();
  const { effective } = useTheme();
  const paramsKey = JSON.stringify(params);
  const prefix = `plugin.${plugin}:`;
  const messages = useMemo(() => {
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(intl.messages)) {
      if (key.startsWith(prefix) && typeof value === "string") out[key.slice(prefix.length)] = value;
    }
    return out;
  }, [intl.messages, prefix]);
  const context = useCallback(
    () => ({
      plugin,
      params: JSON.parse(paramsKey) as Record<string, string>,
      tokens: currentTokens(),
      kit: THEME_KIT,
      scheme: effective.scheme,
      theme: effective.theme.key,
      reducedMotion: effective.reducedMotion,
      language: locale.language,
      direction: locale.direction,
      messages,
    }),
    [plugin, paramsKey, effective, locale.language, locale.direction, messages],
  );
  const started = useRef(false);
  const live = useRef<StreamHandle[]>([]);

  const post = useCallback((message: Record<string, unknown>, transfer: Transferable[] = []) => {
    frame.current?.contentWindow?.postMessage(message, "*", transfer);
  }, []);

  // the member changed their theme, interface or palette (or the language): the view follows
  useEffect(() => {
    if (!started.current) return undefined;
    const raf = requestAnimationFrame(() => post({ type: "context", context: context() }));
    return () => cancelAnimationFrame(raf);
  }, [context, post]);

  // what the listener uses, always the latest (the frame itself lives as long as its place, view and plugin)
  const latest = useRef({ context, onOpen, onClose, run: action.run, navigate });
  latest.current = { context, onOpen, onClose, run: action.run, navigate };

  // biome-ignore lint/correctness/useExhaustiveDependencies: a new place (its parameters) is a new frame
  useEffect(() => {
    const current = frame.current;
    if (!current) return undefined;
    started.current = false; // a new frame (another view, plugin or place) starts again
    let stopped = false;
    const answer = (id: unknown, ok: boolean, value: unknown, error?: { code: string; message: string }) =>
      post({ type: "answer", id, ok, value: ok ? value : null, error: ok ? null : error });
    const listener = async (event: MessageEvent) => {
      if (stopped || event.source !== current.contentWindow) return;
      const data = event.data as Record<string, unknown> | null;
      if (!data || typeof data !== "object" || typeof data.type !== "string") return;
      switch (data.type) {
        case "loaded": {
          if (started.current) return;
          started.current = true;
          const base = `/api/v1/plugins/${plugin}/views/`;
          const source = await fetch(base + view, { credentials: "same-origin" }).then((r) =>
            r.ok ? r.text() : null,
          );
          const css = await fetch(base + view.replace(/\.m?js$/, ".css"), { credentials: "same-origin" })
            .then((r) => (r.ok ? r.text() : ""))
            .catch(() => "");
          if (stopped) return;
          if (source === null) {
            setFailed(true);
            return;
          }
          const fonts = await portalFonts();
          if (stopped) return;
          post({ type: "run", source, css, fonts, context: latest.current.context() });
          return;
        }
        case "error":
          setFailed(true);
          return;
        case "resize":
          if (mode === "page") setHeight(Math.min(20000, Math.max(160, Number(data.height) || 0)));
          return;
        case "call": {
          const method = String(data.method).toUpperCase();
          const path = String(data.path ?? "").replace(/^\/+/, "");
          if (!PATH.test(path) || path.includes("..") || (method !== "GET" && method !== "POST")) {
            answer(data.id, false, null, { code: "refused", message: "not a route of this plugin" });
            return;
          }
          try {
            let value: unknown;
            if (method === "GET") {
              const query = clean(data.query);
              // biome-ignore lint/suspicious/noExplicitAny: plugin routes are declared at runtime
              value = (
                await api.GET(`/api/v1/plugins/${plugin}/${path}` as any, { params: { query } } as any)
              ).data;
            } else {
              const body =
                data.body && typeof data.body === "object" ? (data.body as Record<string, unknown>) : {};
              value = await latest.current.run(path, body);
            }
            answer(data.id, true, value ?? null);
          } catch (error) {
            const code =
              error instanceof Cancelled
                ? "cancelled"
                : error instanceof ApiError
                  ? (error.code ?? "failed")
                  : "failed";
            answer(data.id, false, null, {
              code,
              message: error instanceof Error ? error.message.slice(0, 200) : "failed",
            });
          }
          return;
        }
        case "asset": {
          const path = String(data.path ?? "");
          if (!ASSET.test(path) || path.includes("..")) {
            answer(data.id, false, null, { code: "refused", message: "not a file of this view" });
            return;
          }
          const response = await fetch(`/api/v1/plugins/${plugin}/views/${path}`, {
            credentials: "same-origin",
          });
          if (!response.ok) {
            answer(data.id, false, null, { code: "not_found", message: "not found" });
            return;
          }
          const buffer = await response.arrayBuffer();
          post(
            {
              type: "answer",
              id: data.id,
              ok: true,
              value: { buffer, mime: response.headers.get("content-type") ?? "" },
            },
            [buffer],
          );
          return;
        }
        case "image": {
          const id = String(data.image ?? "");
          if (!/^[0-9a-f-]{32,36}$/.test(id)) {
            answer(data.id, false, null, { code: "refused", message: "not an image of the library" });
            return;
          }
          const response = await fetch(`/api/v1/media/images/${id}`, { credentials: "same-origin" });
          if (!response.ok) {
            answer(data.id, false, null, { code: "not_found", message: "not found" });
            return;
          }
          const buffer = await response.arrayBuffer();
          post(
            {
              type: "answer",
              id: data.id,
              ok: true,
              value: { buffer, mime: response.headers.get("content-type") ?? "" },
            },
            [buffer],
          );
          return;
        }
        case "subscribe": {
          const topic = String(data.topic ?? "");
          if (!NAME.test(topic)) return;
          live.current.push(
            connectStream({
              topics: [`plugin.${plugin}.${topic}`],
              onEvent: (event) => post({ type: "live", topic, data: event.data }),
            }),
          );
          return;
        }
        case "open": {
          const surface = String(data.surface ?? "");
          if (NAME.test(surface)) latest.current.onOpen?.(surface, clean(data.params));
          return;
        }
        case "close":
          latest.current.onClose?.();
          return;
        case "navigate": {
          const link = ownLink(plugin, data.to);
          if (link) latest.current.navigate(link);
          return;
        }
        default:
          return;
      }
    };
    window.addEventListener("message", listener);
    return () => {
      stopped = true;
      window.removeEventListener("message", listener);
      for (const handle of live.current) handle.close();
      live.current = [];
    };
  }, [plugin, view, mode, paramsKey, post]);

  const scheme = { colorScheme: effective.scheme };
  const style =
    mode === "page"
      ? { ...scheme, height }
      : mode === "launcher"
        ? { ...scheme, width: size?.width ?? 56, height: size?.height ?? 56 }
        : scheme;
  return (
    <>
      {failed ? <p role="alert">{intl.formatMessage({ id: "plugins:view.failed" })}</p> : null}
      <iframe
        key={`${plugin}:${view}:${paramsKey}`}
        ref={frame}
        className={`plugin-view plugin-view--${mode}`}
        title={title}
        src={VIEW_SANDBOX}
        sandbox="allow-scripts"
        referrerPolicy="no-referrer"
        style={style}
        hidden={failed}
      />
      {action.dialog}
    </>
  );
}
