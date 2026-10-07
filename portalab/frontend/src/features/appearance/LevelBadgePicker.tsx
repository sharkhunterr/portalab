import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import { LEVEL_BADGES, type LevelBadge } from "../../design-system/a11y/preferences";
import { LevelBadge as Badge } from "../../design-system/components/Badges";
import { useT } from "../../i18n/hooks/useT";
import { InShop } from "./InShop";

/**
 * The level (XP) badge's look (027): the classic one and those the member owns, each shown as worn; how
 * many more the shop sells is said in one line.
 */
export function LevelBadgePicker({ level = 12 }: { level?: number }) {
  const t = useT();
  const { preferences, setPreference } = usePreferences();
  const looks = useQuery({
    queryKey: ["ui", "notification-looks"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/ui/notification-looks")).data as unknown as {
        level_badges?: Array<{ key: string; locked: boolean }>;
      },
  });
  const locked = (key: string) => Boolean(looks.data?.level_badges?.find((p) => p.key === key)?.locked);
  const owned = LEVEL_BADGES.filter((key) => !locked(key));
  return (
    <section className="looks appearance-card" aria-labelledby="level-badge-picker">
      <h3 id="level-badge-picker">{t("notifications:levelBadge.title")}</h3>
      <p className="ds-page-header__context">{t("notifications:levelBadge.hint")}</p>
      <fieldset className="level-badges">
        <legend className="visually-hidden">{t("notifications:levelBadge.title")}</legend>
        {owned.map((key) => {
          const current = preferences.levelBadge === key;
          const name = t(`notifications:levelBadge.names.${key}`);
          return (
            <label key={key} className="level-badges__item" data-current={current || undefined}>
              <input
                type="radio"
                name="level-badge"
                value={key}
                checked={current}
                onChange={() => setPreference("levelBadge", key as LevelBadge)}
              />
              <Badge level={level} label={name} look={key} />
              <span className="looks__name">{name}</span>
            </label>
          );
        })}
      </fieldset>
      <InShop count={LEVEL_BADGES.length - owned.length} type="level_badge" />
    </section>
  );
}
