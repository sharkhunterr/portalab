import { useCallback, useState } from "react";
import { Icon } from "../../../../design-system/components/Icon";
import { FunctionalState } from "../../../../design-system/state/FunctionalState";
import { externalLook, useExternalRevision } from "../../../../design-system/visuals/registry";
import { useT } from "../../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../../i18n/provider/I18nProvider";
import type { ContractValue } from "../../contracts";
import { registerWidgetComponent, type WidgetProps } from "../registry";
import { isForbidden, PackFrame } from "./PackFrame";
import "./pack.css";

/**
 * 028 (US6, R26): a widget a visual pack brings — everything it does is in its pack (its script, run in the
 * sandbox by ``PackFrame``); the portal only tells this page which element to run and which contracts this
 * member may not read. It is handed its own settings as the member chose them. With nothing it may read, or
 * a script that fails, it shows its own words for « empty ».
 */
export const PACK_WIDGET = "visuals.pack";

interface PackData {
  pack?: string;
  look?: string;
  contracts?: string[];
  forbidden?: string[];
}

export function PackWidget({ payload, config, rows }: WidgetProps) {
  const t = useT();
  const { language } = useLocaleContext();
  useExternalRevision(); // the element comes and goes with its pack
  const data = (payload.data ?? {}) as PackData;
  const element = externalLook("widget", data.look);
  const declared = (data.contracts ?? []).filter((key) => element?.contracts?.includes(key));
  const forbidden = data.forbidden ?? [];
  const [failed, setFailed] = useState(false);
  const [values, setValues] = useState<Record<string, ContractValue>>({});
  const onFailed = useCallback(() => setFailed(true), []);
  // nothing it may read: neither by the portal's word nor by the routes' answers
  const empty =
    declared.length > 0 && declared.every((key) => forbidden.includes(key) || isForbidden(values[key]));
  if (!element) return <FunctionalState state="unavailable" />;
  if (empty || failed) {
    const words = element.widget?.empty;
    const said = words?.[language.split("-")[0] ?? "en"] || words?.en || words?.fr;
    return (
      <p className="widget-empty" data-state="no-data" role="status">
        <Icon name="sparkles" size={28} />
        <span>{said || t("dashboard:widgetEmpty")}</span>
      </p>
    );
  }
  return (
    <PackFrame
      element={element}
      declared={declared}
      forbidden={forbidden}
      // its own settings as the member chose them (never the frame's: ``_…``)
      extra={{
        config: Object.fromEntries(Object.entries(config ?? {}).filter(([key]) => !key.startsWith("_"))),
      }}
      rows={rows}
      className="pack-widget"
      onFailed={onFailed}
      onValues={setValues}
    />
  );
}

registerWidgetComponent(PACK_WIDGET, PackWidget);
