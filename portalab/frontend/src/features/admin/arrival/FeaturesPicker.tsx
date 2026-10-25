import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import {
  FEATURES,
  GROUPS,
  type ModuleState,
  type Selection,
  type SettingValue,
  selectionOf,
  useFeatureDraft,
} from "./features";
import "./arrival.css";

/**
 * Issue 246 — the features to keep, as cards to switch on or off by group (what one needs comes with it, what
 * needs it goes with it). Used before the first account exists (a selection kept in memory, applied once the
 * administrator is created) and in the setup assistant (the portal's state, applied with « Apply »).
 */
export function FeaturesPicker({
  selection,
  onChange,
  disabled = false,
}: {
  selection: Selection;
  onChange: (key: string, on: boolean) => void;
  disabled?: boolean;
}) {
  const t = useT();
  return (
    <div className="features-picker">
      {GROUPS.map((group) => (
        <fieldset key={group} className="features-picker__group">
          <legend>{t(`account:features.group.${group}`)}</legend>
          <ul>
            {FEATURES.filter((f) => f.group === group).map((feature) => {
              const on = selection.has(feature.key);
              const id = `feature-${feature.key}`;
              return (
                <li key={feature.key} data-on={on || undefined}>
                  <input
                    id={id}
                    type="checkbox"
                    className="features-picker__check"
                    checked={on}
                    disabled={disabled}
                    aria-describedby={`${id}-hint`}
                    onChange={(e) => onChange(feature.key, e.target.checked)}
                  />
                  <label htmlFor={id} className="features-picker__card">
                    <span className="features-picker__icon" aria-hidden="true">
                      <Icon name={feature.icon} size={20} />
                    </span>
                    <span className="features-picker__text">
                      <strong>{t(`account:features.${feature.key}.title`)}</strong>
                      <span id={`${id}-hint`}>{t(`account:features.${feature.key}.hint`)}</span>
                    </span>
                    <span className="features-picker__mark" aria-hidden="true">
                      {on ? <Icon name="check" size={16} /> : null}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </fieldset>
      ))}
    </div>
  );
}

/** The setup assistant's step: the portal's features as they are, changed and applied here. */
/** The features the portal keeps today, read from its modules and switches. */
export function useCurrentFeatures() {
  return useQuery({
    queryKey: ["admin", "features"],
    queryFn: async () => {
      const [modules, config] = await Promise.all([
        api.GET("/api/v1/admin/modules"),
        api.GET("/api/v1/admin/config"),
      ]);
      return selectionOf(
        (modules.data ?? []) as unknown as ModuleState[],
        ((config.data as unknown as { settings?: SettingValue[] })?.settings ?? []) as SettingValue[],
      );
    },
  });
}

export function PortalFeatures() {
  const t = useT();
  const draft = useFeatureDraft();
  const current = useCurrentFeatures();
  const loaded = useRef(false);
  const { setSelection } = draft;
  useEffect(() => {
    if (current.data && !loaded.current) {
      loaded.current = true;
      setSelection(current.data);
    }
  }, [current.data, setSelection]);
  if (!current.data) return null;
  const changed =
    current.data.size !== draft.selection.size || [...draft.selection].some((k) => !current.data?.has(k));
  return (
    <div className="features-step">
      <FeaturesPicker selection={draft.selection} onChange={draft.set} disabled={draft.state === "saving"} />
      <p className="features-step__actions">
        <Button
          onClick={async () => {
            if (await draft.apply()) void current.refetch();
          }}
          disabled={!changed || draft.state === "saving"}
          aria-busy={draft.state === "saving"}
        >
          <Icon name="check" size={16} />
          {t("account:features.apply")}
        </Button>
        {draft.state === "saved" ? (
          <span role="status" className="features-step__note">
            {t(draft.restart ? "account:features.restart" : "account:features.applied")}
          </span>
        ) : null}
        {draft.state === "error" ? (
          <span role="alert" className="features-step__note">
            {t("account:features.failed")}
          </span>
        ) : null}
      </p>
    </div>
  );
}
