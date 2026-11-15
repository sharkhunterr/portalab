import { useEffect, useId, useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { useT } from "../../i18n/hooks/useT";
import { type HouseholdEconomy as Economy, type Household, useHouseholdEconomy } from "./api";

const CHOICES: { key: Economy; icon: string }[] = [
  { key: "pot", icon: "coins" },
  { key: "dispatch", icon: "users" },
];

/**
 * Issue 443: how the household earns — a common pot on the master's account (each profile keeps its own figures,
 * privately; the master stands for the household in the community, everything its profiles get duplicated on
 * it) or dispatched profiles (each its own wallet, in the community as itself or anonymously). Its master
 * chooses; a profile reads it.
 */
export function HouseholdEconomyChoice({ household }: { household: Household }) {
  const t = useT();
  const notify = useNotify();
  const name = useId();
  const change = useHouseholdEconomy();
  const current = (household.economy ?? "pot") as Economy;
  // the choice holds from the tap until the household read again says it (never back to the old one between)
  const [picked, setPicked] = useState<Economy | null>(null);
  useEffect(() => {
    if (picked && current === picked) setPicked(null);
  }, [current, picked]);
  const shown = picked ?? current;
  if (!household.can_manage)
    return (
      <p className="household-note">
        <Icon name={current === "pot" ? "coins" : "users"} size={14} />{" "}
        {t(`household:economy.mine_${current}`)}
      </p>
    );
  return (
    <fieldset className="household-economy" aria-describedby={`${name}-hint`}>
      <legend>{t("household:economy.title")}</legend>
      <p id={`${name}-hint`} className="household-editor__hint">
        {t("household:economy.hint")}
      </p>
      <div className="household-economy__choices">
        {CHOICES.map((choice) => (
          <label
            key={choice.key}
            className="household-economy__choice"
            data-active={shown === choice.key || undefined}
          >
            <input
              type="radio"
              name={name}
              value={choice.key}
              checked={shown === choice.key}
              disabled={change.isPending}
              onChange={() => {
                setPicked(choice.key);
                change.mutate(choice.key, {
                  onSuccess: () =>
                    notify({ severity: "success", title: t(`household:economy.saved_${choice.key}`) }),
                  onError: () => {
                    setPicked(null);
                    notify({ severity: "critical", title: t("household:error") });
                  },
                });
              }}
            />
            <Icon name={choice.icon} size={18} />
            <span>
              <strong>{t(`household:economy.${choice.key}`)}</strong>
              <small>{t(`household:economy.${choice.key}Hint`)}</small>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
