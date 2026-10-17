import { CheckboxField } from "../../design-system/components/Field";
import { useT } from "../../i18n/hooks/useT";
import { isSafeMode, switchSafeMode } from "../../shell/safeMode";

/** 029: safe mode — Portalab's own interface without anything brought by a pack, in this browser. */
export function SafeModeSwitch() {
  const t = useT();
  return (
    <section className="appearance-card" aria-labelledby="appearance-safe">
      <h3 id="appearance-safe">{t("core:safe.title")}</h3>
      <p className="ds-page-header__context">{t("core:safe.hint")}</p>
      <CheckboxField
        label={t("core:safe.switch")}
        checked={isSafeMode()}
        onChange={(event) => switchSafeMode(event.target.checked)}
      />
    </section>
  );
}
