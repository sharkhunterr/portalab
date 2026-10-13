import { LEVEL_BADGES } from "../../design-system/a11y/preferences";
import { LevelBadge as Badge } from "../../design-system/components/Badges";
import { useNotify } from "../../design-system/components/Notification";
import { useT } from "../../i18n/hooks/useT";
import { useEquipLook, useProfileLooks } from "../community/profile/looks";
import { useProgression } from "../gamification/api";
import { InShop } from "./InShop";
import { HdTag, isHdLevelBadge, RarityTag, rarityIn } from "./Rarity";
import { WaitingTag, waitingIn } from "./waiting";

/**
 * The level (XP) badge's look (027): worn on the profile — everyone sees it, in the header, the navigation
 * and on the profile. « Classic » changes with the level; the others the member owns (bought in the shop or
 * given by an achievement) are shown as worn at their level; how many more the shop sells is said in one
 * line.
 */
export function LevelBadgePicker() {
  const t = useT();
  const notify = useNotify();
  const looks = useProfileLooks();
  const equip = useEquipLook();
  const progression = useProgression();
  const level = progression.data?.level ?? 12;
  const locked = (key: string) => Boolean(looks.data?.levels?.find((p) => p.key === key)?.locked);
  // #99: those won but waiting for a level show too, locked, with what they wait for
  const owned = LEVEL_BADGES.filter((key) => !locked(key) || waitingIn(looks.data?.levels, key));
  const worn = looks.data?.equipped?.level ?? "classic";
  return (
    <section className="looks appearance-card" aria-labelledby="level-badge-picker">
      <h3 id="level-badge-picker">{t("notifications:levelBadge.title")}</h3>
      <p className="ds-page-header__context">{t("notifications:levelBadge.hint")}</p>
      <fieldset className="level-badges">
        <legend className="visually-hidden">{t("notifications:levelBadge.title")}</legend>
        {owned.map((key) => {
          const current = worn === key;
          const name = t(`notifications:levelBadge.names.${key}`);
          const waiting = waitingIn(looks.data?.levels, key);
          return (
            <label
              key={key}
              className="level-badges__item"
              data-current={current || undefined}
              data-rarity={rarityIn(looks.data?.levels, key)}
              data-waiting={waiting ? "true" : undefined}
            >
              <RarityTag rarity={rarityIn(looks.data?.levels, key)} />
              <input
                type="radio"
                name="level-badge"
                value={key}
                checked={current}
                disabled={equip.isPending || Boolean(waiting)}
                onChange={() =>
                  equip.mutate(
                    { slot: "level", value: key === "classic" ? null : key },
                    { onError: () => notify({ severity: "warning", title: t("community:looks.failed") }) },
                  )
                }
              />
              <Badge level={level} label={name} look={key} />
              <span className="looks__name">
                {name}
                {isHdLevelBadge(key) ? <HdTag /> : null}
                {waiting ? <WaitingTag waiting={waiting} /> : null}
              </span>
            </label>
          );
        })}
      </fieldset>
      <p className="ds-field__hint">{t("notifications:levelBadge.tiers")}</p>
      <InShop count={LEVEL_BADGES.length - owned.length} type="level_badge" />
    </section>
  );
}
