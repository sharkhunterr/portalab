import { createContext, type ReactNode, useCallback, useContext, useState } from "react";
import { type ExternalElement, externalLooks } from "../../../../design-system/visuals/registry";
import { type Instance, useWidgetData } from "../../api";
import { PackFrame } from "./PackFrame";

/**
 * 028 (US6): the options packs bring a widget — Portalab's or a pack's — that this member put on it
 * (``_options``; the server leaves out those not owned). A stylesheet one dresses it under
 * ``[data-widget-option~="<look>"]`` (animations, another look); a script one shows the widget otherwise (with
 * its own data and more: ``place: replace``) or draws over it (``overlay``), in the sandbox, handed the
 * widget's data and settings and the contracts it declared. Everything they do is in their pack.
 */
export function wornAddons(instance: Instance): ExternalElement[] {
  const worn = (instance.config as { _options?: unknown } | undefined)?._options;
  if (!Array.isArray(worn) || !worn.length) return [];
  return externalLooks("widget_option").filter(
    (option) =>
      option.look &&
      worn.includes(option.look) &&
      !option.widget?.setting &&
      (!option.widget?.for || option.widget.for === instance.widget_key),
  );
}

/** The add-ons a member may put on this widget (live ones aimed at it or at every widget). */
export function addonsFor(widgetKey: string): ExternalElement[] {
  return externalLooks("widget_option").filter(
    (option) =>
      option.look && !option.widget?.setting && (!option.widget?.for || option.widget.for === widgetKey),
  );
}

/** issue 225: the option a widget's region is given to (``place: stage``), for the component keeping one. */
export const StageContext = createContext<{ instance: Instance; element: ExternalElement } | null>(null);

/**
 * issue 225: the region a widget keeps for an option's script (the daily wheel's face): the script worn, in
 * its sandbox, handed also ``stage`` (what the widget says of the moment: a spin's phase…); ``fallback`` —
 * Portalab's own drawing — when none is worn or it fails.
 */
export function WidgetStage({ fallback, stage }: { fallback: ReactNode; stage?: Record<string, unknown> }) {
  const worn = useContext(StageContext);
  const [failed, setFailed] = useState(false);
  if (!worn || failed) return <>{fallback}</>;
  return (
    <AddonFrame
      instance={worn.instance}
      element={worn.element}
      more={stage ? { stage } : undefined}
      className="pack-addon pack-addon--stage"
      onFailed={() => setFailed(true)}
    />
  );
}

export function AddonFrame({
  instance,
  element,
  rows,
  onFailed,
  more,
  className,
}: {
  instance: Instance;
  element: ExternalElement;
  rows?: number | undefined;
  onFailed?: () => void;
  /** what the widget adds for it (a stage's phase) */
  more?: Record<string, unknown> | undefined;
  className?: string;
}) {
  // the widget's own data: the frame's query, shared (never read twice)
  const query = useWidgetData(instance.widget_key, instance.id ?? null, null);
  const [failed, setFailed] = useState(false);
  const fail = useCallback(() => {
    setFailed(true);
    onFailed?.();
  }, [onFailed]);
  if (failed) return null;
  const config = Object.fromEntries(
    Object.entries(instance.config ?? {}).filter(([key]) => !key.startsWith("_")),
  );
  return (
    <PackFrame
      element={element}
      declared={element.contracts ?? []}
      forbidden={[]}
      extra={{
        widget: {
          key: instance.widget_key,
          state: query.data?.state ?? (query.isError ? "error" : "loading"),
          data: query.data?.data ?? null,
        },
        config,
        ...(more ?? {}),
      }}
      rows={rows}
      className={
        className ?? (element.widget?.place === "replace" ? "pack-widget" : "pack-addon pack-addon--overlay")
      }
      onFailed={fail}
    />
  );
}
