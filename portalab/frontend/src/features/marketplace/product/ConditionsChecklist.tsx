import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";

interface Check {
  name: string;
  value: unknown;
  met: boolean;
  reason: string;
}

/** Conditions by name (spec 015 T024): each one met or not, in text with an icon — never color alone. */
export function ConditionsChecklist({ checks }: { checks: Check[] }) {
  const t = useT();
  if (checks.length === 0) return <p>{t("marketplace:conditions.none")}</p>;
  return (
    <ul className="ds-stack" aria-label={t("marketplace:conditions.title")}>
      {checks.map((check) => (
        <li key={`${check.name}-${String(check.value)}`}>
          <FunctionalState
            state={check.met ? "available" : check.reason === "unavailable" ? "unavailable" : "error"}
            label={`${t(`marketplace:conditions.${check.name}`, { value: String(check.value) })} — ${
              check.met
                ? t("marketplace:conditions.met")
                : check.reason === "unavailable"
                  ? t("marketplace:conditions.unavailable")
                  : t("marketplace:conditions.unmet")
            }`}
          />
        </li>
      ))}
    </ul>
  );
}
