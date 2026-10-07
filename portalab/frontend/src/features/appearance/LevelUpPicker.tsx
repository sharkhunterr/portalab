import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import { LEVEL_UPS, type LevelUpLook } from "../../design-system/a11y/preferences";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useProgression } from "../gamification/api";
import { showLevelUp } from "../gamification/levelup/LevelUpMoment";
import { InShop } from "./InShop";

/**
 * How a level-up is shown (027): the classic moment and those the member owns — each can be tried; how
 * many more the shop sells is said in one line.
 */
export function LevelUpPicker() {
  const t = useT();
  const { preferences, setPreference } = usePreferences();
  const level = (useProgression().data?.level ?? 11) + 1;
  const looks = useQuery({
    queryKey: ["ui", "notification-looks"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/ui/notification-looks")).data as unknown as {
        level_ups?: Array<{ key: string; locked: boolean }>;
      },
  });
  const locked = (key: string) => Boolean(looks.data?.level_ups?.find((p) => p.key === key)?.locked);
  const owned = LEVEL_UPS.filter((key) => !locked(key));
  return (
    <section className="looks appearance-card" aria-labelledby="level-up-picker">
      <h3 id="level-up-picker">{t("notifications:levelUp.title")}</h3>
      <p className="ds-page-header__context">{t("notifications:levelUp.hint")}</p>
      <fieldset className="looks__animations">
        <legend className="visually-hidden">{t("notifications:levelUp.title")}</legend>
        {owned.map((key) => (
          <label key={key} className="looks__chip" data-current={preferences.levelUp === key || undefined}>
            <input
              type="radio"
              name="level-up"
              value={key}
              checked={preferences.levelUp === key}
              onChange={() => setPreference("levelUp", key as LevelUpLook)}
            />
            <Icon name="trophy" size={14} />
            {t(`notifications:levelUp.names.${key}`)}
          </label>
        ))}
      </fieldset>
      <p className="looks__more">
        <Button variant="secondary" onClick={() => showLevelUp({ level, preview: preferences.levelUp })}>
          <Icon name="sparkles" size={16} />
          {t("notifications:levelUp.try")}
        </Button>
      </p>
      <InShop count={LEVEL_UPS.length - owned.length} type="level_up" />
    </section>
  );
}
