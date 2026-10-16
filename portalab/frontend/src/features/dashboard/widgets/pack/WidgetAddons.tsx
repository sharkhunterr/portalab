import { useCallback, useState } from "react";
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

export function AddonFrame({
  instance,
  element,
  rows,
  onFailed,
}: {
  instance: Instance;
  element: ExternalElement;
  rows?: number | undefined;
  onFailed?: () => void;
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
      }}
      rows={rows}
      className={element.widget?.place === "overlay" ? "pack-addon pack-addon--overlay" : "pack-widget"}
      onFailed={fail}
    />
  );
}
