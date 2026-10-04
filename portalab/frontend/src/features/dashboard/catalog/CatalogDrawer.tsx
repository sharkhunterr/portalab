import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Drawer } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Change, useCatalog } from "../api";

/** Widget catalog (spec 009 T019): only widgets the user may add (permitted, enabled, entitled, allowed by policy). */
export function CatalogDrawer({ apply }: { apply: (change: Change) => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const catalog = useCatalog(open);
  return (
    <Drawer
      open={open}
      onOpenChange={setOpen}
      title={t("dashboard:catalog")}
      closeLabel={t("dashboard:done")}
      trigger={
        <Button variant="secondary">
          <Icon name="plus" size={18} />
          {t("dashboard:addWidget")}
        </Button>
      }
    >
      {catalog.isPending ? <FunctionalState state="loading" /> : null}
      {catalog.isError ? <FunctionalState state="error" onRetry={() => catalog.refetch()} /> : null}
      <ul className="dashboard-catalog widget-gallery">
        {(catalog.data ?? []).map((entry) => {
          const disabled = entry.placed && !entry.widget.multiple;
          return (
            <li key={entry.key} className="widget-gallery__item">
              <span
                className="widget-gallery__preview"
                data-template={entry.widget.template ?? "custom"}
                aria-hidden="true"
              >
                <Icon name={entry.widget.icon ?? "dashboard"} size={26} />
              </span>
              <span className="widget-gallery__text">
                <strong>{t(entry.widget.title_key)}</strong>
                {entry.widget.description_key ? <span>{t(entry.widget.description_key)}</span> : null}
                <span className="widget__meta">
                  {t("dashboard:gallery.size", { w: entry.widget.min_w, h: entry.widget.min_h })} –{" "}
                  {t("dashboard:gallery.size", { w: entry.widget.max_w, h: entry.widget.max_h })}
                </span>
              </span>
              <Button
                variant="secondary"
                disabled={disabled}
                aria-label={`${t("dashboard:add")} ${t(entry.widget.title_key)}`}
                onClick={() => apply({ kind: "add", widget_key: entry.key })}
              >
                {disabled ? t("dashboard:added") : t("dashboard:add")}
              </Button>
            </li>
          );
        })}
      </ul>
    </Drawer>
  );
}
