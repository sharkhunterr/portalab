import { useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { SavedNote, SettingsCard, SettingsPage } from "../account/SettingsKit";
import { PLAY, type Play, usePlay } from "../onboarding/play";
import "../onboarding/onboarding.css";

/**
 * « Play » (issue 14, issue 243): the welcome's « do you want to play? », changed at any time — all of it,
 * without the Mediacards (they are hidden, no card booster is given by watching), or not at all (an anonymous
 * profile). The looks boosters, the progression and the shop stay whatever the answer.
 */
export default function PlaySettings() {
  const t = useT();
  const [done, setDone] = useState(false);
  const { saved, save } = usePlay(() => setDone(true));
  const current: Play = saved ?? "full";
  return (
    <SettingsPage
      icon="gamepad"
      title={t("account:settings.page.play")}
      lead={t("account:settings.playLead")}
    >
      <SettingsCard
        icon="gamepad"
        title={t("onboarding:play.title")}
        hint={t("onboarding:play.lead")}
        aside={<SavedNote shown={done && !save.isPending} text={t("account:saved")} />}
        level={2}
      >
        <fieldset className="onboarding-play settings-play" disabled={save.isPending}>
          <legend className="visually-hidden">{t("onboarding:play.title")}</legend>
          {PLAY.map((choice) => (
            <label
              key={choice.key}
              className="onboarding-play__choice"
              data-current={current === choice.key || undefined}
            >
              <input
                type="radio"
                name="settings-play"
                value={choice.key}
                checked={current === choice.key}
                onChange={() => {
                  setDone(false);
                  save.mutate(choice.key);
                }}
              />
              <span className="onboarding-play__icon" aria-hidden="true">
                <Icon name={choice.icon} size={20} />
              </span>
              <span className="onboarding-play__text">
                <strong>{t(`onboarding:play.${choice.key}`)}</strong>
                <span>{t(`account:settings.play.${choice.key}`)}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {save.error ? (
          <p className="settings-play__problem" role="alert">
            {t("onboarding:play.error")}
          </p>
        ) : null}
        <p className="settings-play__more">
          <Link to="/privacy">{t("account:settings.playPrivacy")}</Link>
        </p>
      </SettingsCard>
    </SettingsPage>
  );
}
