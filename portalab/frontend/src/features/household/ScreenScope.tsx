import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";

export type Scope = "media" | "portal";
const SCOPES: readonly Scope[] = ["media", "portal"];
const ICONS: Record<Scope, string> = { media: "play", portal: "dashboard" };

/** Issue 439: what a profile's screen time counts — its media (watched, read, listened to, played), or every
 * minute it spends on Portalab. */
export function ScreenScope({
  name,
  value,
  onChange,
}: {
  name: string;
  value: Scope | undefined;
  onChange: (scope: Scope) => void;
}) {
  const t = useT();
  const current = value ?? "media";
  return (
    <fieldset className="household-editor__modes">
      <legend className="household-editor__label">{t("household:scope.title")}</legend>
      {SCOPES.map((scope) => (
        <label key={scope} data-checked={current === scope || undefined}>
          <input
            type="radio"
            name={name}
            value={scope}
            checked={current === scope}
            onChange={() => onChange(scope)}
          />
          <Icon name={ICONS[scope]} size={18} />
          <span>
            <strong>{t(`household:scope.${scope}`)}</strong>
            <small>{t(`household:scope.${scope}Hint`)}</small>
          </span>
        </label>
      ))}
    </fieldset>
  );
}
