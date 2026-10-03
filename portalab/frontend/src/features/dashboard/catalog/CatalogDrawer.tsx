import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
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
      trigger={<Button>{t("dashboard:addWidget")}</Button>}
    >
      {catalog.isPending ? <FunctionalState state="loading" /> : null}
      {catalog.isError ? <FunctionalState state="error" onRetry={() => catalog.refetch()} /> : null}
      <ul className="dashboard-catalog">
        {(catalog.data ?? []).map((entry) => {
          const disabled = entry.placed && !entry.widget.multiple;
          return (
            <li key={entry.key}>
              <strong>{t(entry.widget.title_key)}</strong>
              {entry.widget.description_key ? <p>{t(entry.widget.description_key)}</p> : null}
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
