import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useShellPreference } from "../../shell/preferences";

/**
 * First-visit welcome (spec 027 FR-029, R22): introduces the header, the sections and the themes; once
 * dismissed it never comes back, on any device (``shell.welcome.dismissedAt``, account-level).
 */
export function WelcomeCard() {
  const t = useT();
  const [dismissedAt, setDismissedAt] = useShellPreference<string | null>("shell.welcome.dismissedAt", null);
  if (dismissedAt) return null;
  return (
    <section className="ds-card welcome-card" aria-labelledby="welcome-card-title">
      <span className="welcome-card__art" aria-hidden="true">
        <Icon name="sparkles" size={30} />
      </span>
      <div className="welcome-card__body">
        <h2 id="welcome-card-title">{t("dashboard:welcome.title")}</h2>
        <ul>
          <li>
            <Icon name="trophy" size={18} /> {t("dashboard:welcome.header")}
          </li>
          <li>
            <Icon name="menu" size={18} /> {t("dashboard:welcome.menu")}
          </li>
          <li>
            <Icon name="palette" size={18} /> {t("dashboard:welcome.theme")}
          </li>
        </ul>
        <div className="welcome-card__actions">
          <Link className="ds-button ds-button--secondary" to="/settings/appearance">
            {t("dashboard:welcome.chooseTheme")}
          </Link>
          <Button onClick={() => setDismissedAt(new Date().toISOString())}>
            {t("dashboard:welcome.dismiss")}
          </Button>
        </div>
      </div>
    </section>
  );
}
