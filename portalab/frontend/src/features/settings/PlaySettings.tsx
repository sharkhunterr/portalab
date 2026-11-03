import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { SavedNote, SettingsCard, SettingsPage } from "../account/SettingsKit";
import { PlayScale } from "../onboarding/PlayScale";
import { usePlay, useProfileDashboard } from "../onboarding/play";
import "../onboarding/onboarding.css";

/**
 * « Play » (issue 14, issue 243): the welcome's « do you want to play? », changed at any time. Issue 347: the
 * play gauge — just the media (an anonymous profile, no cards, games nor quests in the menu), passive (the
 * progression), collector (and the Mediacards), keen (and the day's games) — and the dashboard the
 * administrator prepared for it, taken on demand (it replaces the member's own arrangement).
 */
export default function PlaySettings() {
  const t = useT();
  const [done, setDone] = useState(false);
  const { saved, save } = usePlay(() => setDone(true));
  const dashboard = useProfileDashboard();
  const current = saved ?? "full";
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
        <PlayScale
          value={current}
          disabled={save.isPending}
          onChange={(play) => {
            setDone(false);
            save.mutate(play);
          }}
        />
        {save.error ? (
          <p className="settings-play__problem" role="alert">
            {t("onboarding:play.error")}
          </p>
        ) : null}
        <p className="settings-play__more">
          <Link to="/privacy">{t("account:settings.playPrivacy")}</Link>
        </p>
      </SettingsCard>
      <SettingsCard
        icon="dashboard"
        title={t("onboarding:play.dashboard")}
        hint={t("onboarding:play.dashboardReplace")}
        aside={<SavedNote shown={dashboard.isSuccess} text={t("account:settings.playDashboardDone")} />}
        level={2}
      >
        <div className="settings-actions">
          <Button variant="secondary" disabled={dashboard.isPending} onClick={() => dashboard.mutate()}>
            <Icon name="dashboard" size={16} />
            {t("account:settings.playDashboard")}
          </Button>
        </div>
        {dashboard.error ? (
          <p className="settings-play__problem" role="alert">
            {t("onboarding:play.error")}
          </p>
        ) : null}
      </SettingsCard>
    </SettingsPage>
  );
}
