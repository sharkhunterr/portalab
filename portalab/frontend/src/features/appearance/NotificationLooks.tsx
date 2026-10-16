import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { NotificationAnimation, NotificationStyle } from "../../design-system/a11y/preferences";
import { Button } from "../../design-system/components/Button";
import { FxLayer } from "../../design-system/components/Fx";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { useTheme } from "../../design-system/themes/ThemeProvider";
import { gpuLook } from "../../design-system/visuals/gpu";
import { useExternalRevision } from "../../design-system/visuals/registry";
import { useT } from "../../i18n/hooks/useT";
import { InShop } from "./InShop";
import { RarityTag, rarityIn } from "./Rarity";
import { type Waiting, WaitingTag, waitingIn } from "./waiting";
import "./notification-looks.css";

/**
 * Notification looks (027): the style (shape and layout) and the animation of notifications, chosen with a
 * live preview, independent of the theme — only the member's own (the server refuses the others anyway);
 * how many more the shop sells is said in one line. « Try it » shows a sample notification right away.
 */
interface Choice {
  key: string;
  locked: boolean;
  rarity?: string | null;
  waiting?: Waiting | null;
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

export function NotificationLooks({ position }: { position?: ReactNode }) {
  const t = useT();
  const notify = useNotify();
  const { preferences, setPreference } = usePreferences();
  const looks = useLooks();
  useExternalRevision(); // 028: the styles' packs read, their GPU looks drawn
  const themeNotification = useTheme().effective.theme.notification;
  const locked = (list: Choice[] | undefined, key: string) =>
    Boolean(list?.find((c) => c.key === key)?.locked);
  // 027: the theme's own look is worn with its universe's pack; without it the free default shows
  const ownStyle = themeNotification?.style ?? "toast";
  const themeStyle = locked(looks.data?.styles, ownStyle) ? "toast" : ownStyle;
  const inPack =
    locked(looks.data?.styles, ownStyle) ||
    locked(looks.data?.animations, themeNotification?.animation ?? "slide");
  const gpuOf = (style: string) => gpuLook("notification_style", style === "theme" ? themeStyle : style);
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
  const lockedCount = (list: Choice[] | undefined) =>
    (list ?? []).filter((c) => c.locked && !c.waiting).length;
  // 028: the looks are the visual packs' (Portalab's own included): the server lists them
  const keysOf = (list: Choice[] | undefined) => (list ?? []).map((c) => c.key);
  // #99: those won but waiting for a level show too, locked
  const styles = ["theme", ...keysOf(looks.data?.styles)].filter(
    (style) =>
      style === "theme" || !locked(looks.data?.styles, style) || waitingIn(looks.data?.styles, style),
  );
  const animations = ["theme", ...keysOf(looks.data?.animations)].filter(
    (animation) =>
      animation === "theme" ||
      !locked(looks.data?.animations, animation) ||
      waitingIn(looks.data?.animations, animation),
  );
  return (
    <section className="looks appearance-card" aria-labelledby="notification-looks">
      <div className="looks__head">
        <h3 id="notification-looks">{t("notifications:looks.title")}</h3>
        <Button variant="secondary" onClick={tryIt}>
          <Icon name="bell" size={16} />
          {t("notifications:looks.try")}
        </Button>
      </div>
      <p className="ds-page-header__context">{t("notifications:looks.hint")}</p>
      {position}
      <fieldset className="looks__styles">
        <legend>{t("notifications:looks.style")}</legend>
        {styles.map((style) => {
          const current = preferences.notificationStyle === style;
          const waiting = waitingIn(looks.data?.styles, style);
          return (
            <label
              key={style}
              className="looks__style"
              data-current={current || undefined}
              data-waiting={waiting ? "true" : undefined}
              data-rarity={rarityIn(looks.data?.styles, style)}
            >
              <RarityTag rarity={rarityIn(looks.data?.styles, style)} />
              <input
                type="radio"
                name="notification-style"
                value={style}
                checked={current}
                disabled={Boolean(waiting)}
                onChange={() => setPreference("notificationStyle", style as NotificationStyle | "theme")}
              />
              <span
                className="looks__preview ds-notifications"
                data-style={style === "theme" ? themeStyle : style}
                aria-hidden="true"
              >
                <span
                  className="ds-notification"
                  data-tone="info"
                  data-fx={gpuLook("notification_style", style === "theme" ? themeStyle : style)?.effect}
                >
                  {gpuOf(style) ? (
                    <FxLayer effect={gpuOf(style)?.effect ?? ""} calm shape={gpuOf(style)?.shape ?? 0} />
                  ) : null}
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
                {style === "theme"
                  ? t("notifications:universe.followTheme")
                  : t(`notifications:looks.styles.${style}`)}
              </span>
              {waiting ? <WaitingTag waiting={waiting} /> : null}
            </label>
          );
        })}
      </fieldset>
      <InShop count={lockedCount(looks.data?.styles)} type="notification_style" />
      <fieldset className="looks__animations">
        <legend>{t("notifications:looks.animation")}</legend>
        {animations.map((animation) => {
          const current = preferences.notificationAnimation === animation;
          const waiting = waitingIn(looks.data?.animations, animation);
          return (
            <label
              key={animation}
              className="looks__chip"
              data-current={current || undefined}
              data-waiting={waiting ? "true" : undefined}
              data-rarity={rarityIn(looks.data?.animations, animation)}
            >
              <input
                type="radio"
                name="notification-animation"
                value={animation}
                checked={current}
                disabled={Boolean(waiting)}
                onChange={() => {
                  setPreference("notificationAnimation", animation as NotificationAnimation | "theme");
                  setTimeout(tryIt, 50); // see it right away
                }}
              />
              <Icon name="sparkles" size={14} />
              {animation === "theme"
                ? t("notifications:universe.followTheme")
                : t(`notifications:looks.animations.${animation}`)}
              <RarityTag rarity={rarityIn(looks.data?.animations, animation)} />
              {waiting ? <WaitingTag waiting={waiting} /> : null}
            </label>
          );
        })}
      </fieldset>
      <InShop count={lockedCount(looks.data?.animations)} type="notification_animation" />
      {inPack ? <p className="looks__more">{t("notifications:universe.themeLookInPack")}</p> : null}
    </section>
  );
}
