import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { switchSafeMode } from "../safeMode";

/** 029: safe mode said, and left in one click. */
export function SafeModeBanner() {
  const t = useT();
  return (
    <div className="maintenance-banner" role="status" data-safe="true">
      <Icon name="shield" size={16} />
      <span>{t("core:safe.on")}</span>
      <Button variant="ghost" onClick={() => switchSafeMode(false)}>
        {t("core:safe.leave")}
      </Button>
    </div>
  );
}
