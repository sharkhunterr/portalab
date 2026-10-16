import { useEffect, useRef } from "react";
import { useTheme } from "../../../../design-system/themes/ThemeProvider";
import type { ExternalElement } from "../../../../design-system/visuals/registry";
import { reportFailure, runSandbox, type Sandbox } from "../../../../design-system/visuals/sandbox";
import { useLocaleContext } from "../../../../i18n/provider/I18nProvider";
import { type ContractValue, useContracts } from "../../contracts";

const READY_MS = 4000;
const COLOURS = ["bg", "surface", "surface-raised", "text", "text-muted", "accent", "accent-alt", "border"];

/**
 * 028 (US6, R26): a pack's script for the dashboard — a widget of its own or an option a widget wears — in
 * its sandbox (an iframe of an opaque origin: no network, no session, no page of Portalab's). It never asks
 * the portal anything: this page reads the data contracts it declared (only those, only those this member
 * may read) through the portal's usual routes and posts it their fields, with what it is shown on (``extra``:
 * a widget's own data and settings), the interface's colours and fonts, the language, its size and whether
 * the member asked for less motion; and again whenever any of it changes. Decorative for assistive
 * technologies (its widget keeps its title); a script that never starts or stops answering is reported and
 * ``onFailed`` lets its host fall back.
 */
export function PackFrame({
  element,
  declared,
  forbidden,
  extra,
  rows,
  className,
  onFailed,
  onValues,
}: {
  element: ExternalElement;
  declared: readonly string[];
  forbidden: readonly string[];
  extra?: Record<string, unknown>;
  rows?: number | undefined;
  className: string;
  onFailed: () => void;
  onValues?: (values: Record<string, ContractValue>) => void;
}) {
  const { language } = useLocaleContext();
  const { effective: theme } = useTheme();
  // only what the element declares (never more than it was reviewed with)
  const values = useContracts(
    declared.filter((key) => element.contracts?.includes(key)),
    forbidden,
  );
  const frame = useRef<HTMLIFrameElement>(null);
  const sandbox = useRef<Sandbox | null>(null);
  const failed = useRef(onFailed);
  failed.current = onFailed;
  const context = () => {
    const style = getComputedStyle(document.documentElement);
    const box = frame.current?.getBoundingClientRect();
    return {
      type: element.type,
      look: element.look,
      ...(extra ?? {}),
      data: values,
      size: sizeOf(box, rows),
      colors: Object.fromEntries(
        COLOURS.map((name) => [name, style.getPropertyValue(`--color-${name}`).trim()]),
      ),
      fonts: {
        body: theme.theme.typography?.fontFamily ?? "system-ui, sans-serif",
        heading: theme.theme.typography?.headingFamily ?? "system-ui, sans-serif",
      },
      locale: language,
      reducedMotion: theme.reducedMotion,
    };
  };
  const latest = useRef(context);
  latest.current = context;
  useEffect(() => onValues?.(values), [values, onValues]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: one sandbox per element (its version)
  useEffect(() => {
    const target = frame.current;
    if (!target) return;
    let ready = false;
    const timer = window.setTimeout(() => {
      if (ready) return;
      reportFailure(element, "timeout");
      failed.current();
    }, READY_MS);
    sandbox.current = runSandbox(target, element, latest.current(), {
      onReady: () => {
        ready = true;
      },
      onError: () => failed.current(),
    });
    return () => {
      window.clearTimeout(timer);
      sandbox.current?.stop();
      sandbox.current = null;
    };
  }, [element.pack, element.sha, element.look, element.type]);

  // what it knows changed: its data, what it is shown on, the language, the motion, its size
  const known = JSON.stringify([values, extra, language, theme.reducedMotion, rows]);
  // biome-ignore lint/correctness/useExhaustiveDependencies: posted again only when what it knows changes
  useEffect(() => {
    sandbox.current?.update(latest.current());
  }, [known]);
  useEffect(() => {
    const target = frame.current;
    if (!target || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => sandbox.current?.update(latest.current()));
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  return (
    <iframe
      ref={frame}
      className={className}
      data-sandboxed=""
      data-external={element.product}
      sandbox="allow-scripts"
      title={element.names[language.split("-")[0] ?? "en"] || element.names.en || element.product}
      aria-hidden="true"
      tabIndex={-1}
    />
  );
}

/**
 * The space it has, and its form — what it draws for each is its own: ``line`` (one row: the essentials on a
 * line), ``column`` (narrow: stacked), ``tall`` (three rows or more: room for more), ``block`` otherwise.
 */
export function sizeOf(box: { width: number; height: number } | undefined, rows: number | undefined) {
  const width = Math.round(box?.width ?? 0);
  const height = Math.round(box?.height ?? 0);
  const form =
    rows !== undefined && rows <= 1
      ? "line"
      : width > 0 && width < 260
        ? "column"
        : rows !== undefined && rows >= 3
          ? "tall"
          : "block";
  return { width, height, rows: rows ?? null, form };
}

export function isForbidden(value: ContractValue): boolean {
  return typeof value === "object" && value !== null && (value as { state?: unknown }).state === "forbidden";
}
