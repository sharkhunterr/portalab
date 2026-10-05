import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import {
  NOTIFICATION_ANIMATIONS,
  NOTIFICATION_STYLES,
  type NotificationAnimation,
  type NotificationStyle,
} from "../../design-system/a11y/preferences";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { useT } from "../../i18n/hooks/useT";
import "./notification-looks.css";

/**
 * Notification looks (027): the style (shape and layout) and the animation of notifications, chosen with a
 * live preview, independent of the theme. Those sold in the shop are shown locked with a link to buy them
 * (the server refuses them to non-owners anyway). « Try it » shows a sample notification right away.
 */
interface Choice {
  key: string;
  locked: boolean;
}

function useLooks() {
  return useQuery({
    queryKey: ["ui", "notification-looks"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/ui/notification-looks")).data as unknown as {
        styles: Choice[];
        animations: Choice[];
      },
  });
}

export function NotificationLooks() {
  const t = useT();
  const notify = useNotify();
  const { preferences, setPreference } = usePreferences();
  const looks = useLooks();
  const locked = (list: Choice[] | undefined, key: string) =>
    Boolean(list?.find((c) => c.key === key)?.locked);
  const tryIt = () =>
    notify({
      severity: "success",
      tone: "reward",
      title: t("notifications:looks.sampleTitle"),
      body: t("notifications:looks.sampleBody"),
      badge: t("notifications:badge.reward"),
      href: "/progression",
      linkLabel: t("notifications:open"),
    });
  return (
    <section className="looks" aria-labelledby="notification-looks">
      <div className="looks__head">
        <h3 id="notification-looks">{t("notifications:looks.title")}</h3>
        <Button variant="secondary" onClick={tryIt}>
          <Icon name="bell" size={16} />
          {t("notifications:looks.try")}
        </Button>
      </div>
      <p className="ds-page-header__context">{t("notifications:looks.hint")}</p>
      <fieldset className="looks__styles">
        <legend>{t("notifications:looks.style")}</legend>
        {NOTIFICATION_STYLES.map((style) => {
          const isLocked = locked(looks.data?.styles, style);
          const current = preferences.notificationStyle === style;
          return (
            <label
              key={style}
              className="looks__style"
              data-current={current || undefined}
              data-locked={isLocked || undefined}
            >
              <input
                type="radio"
                name="notification-style"
                value={style}
                checked={current}
                disabled={isLocked}
                onChange={() => setPreference("notificationStyle", style as NotificationStyle)}
              />
              <span className="looks__preview ds-notifications" data-style={style} aria-hidden="true">
                <span className="ds-notification" data-tone="info">
                  <span className="ds-notification__icon">
                    <Icon name="bell" size={14} />
                  </span>
                  <span className="ds-notification__content">
                    <span className="looks__line" />
                    <span className="looks__line looks__line--short" />
                  </span>
                </span>
              </span>
              <span className="looks__name">
                {t(`notifications:looks.styles.${style}`)}
                {isLocked ? <Icon name="lock" size={14} /> : null}
              </span>
              {isLocked ? (
                <Link className="looks__shop" to="/marketplace?type=notification_style">
                  {t("notifications:looks.inShop")}
                </Link>
              ) : null}
            </label>
          );
        })}
      </fieldset>
      <fieldset className="looks__animations">
        <legend>{t("notifications:looks.animation")}</legend>
        {NOTIFICATION_ANIMATIONS.map((animation) => {
          const isLocked = locked(looks.data?.animations, animation);
          const current = preferences.notificationAnimation === animation;
          return (
            <label
              key={animation}
              className="looks__chip"
              data-current={current || undefined}
              data-locked={isLocked || undefined}
            >
              <input
                type="radio"
                name="notification-animation"
                value={animation}
                checked={current}
                disabled={isLocked}
                onChange={() => {
                  setPreference("notificationAnimation", animation as NotificationAnimation);
                  setTimeout(tryIt, 50); // see it right away
                }}
              />
              {isLocked ? <Icon name="lock" size={14} /> : <Icon name="sparkles" size={14} />}
              {t(`notifications:looks.animations.${animation}`)}
            </label>
          );
        })}
      </fieldset>
      {[...(looks.data?.styles ?? []), ...(looks.data?.animations ?? [])].some((c) => c.locked) ? (
        <p className="looks__more">
          <Icon name="shop" size={16} />
          {t("notifications:looks.more")} <Link to="/marketplace">{t("notifications:looks.toShop")}</Link>
        </p>
      ) : null}
    </section>
  );
}
