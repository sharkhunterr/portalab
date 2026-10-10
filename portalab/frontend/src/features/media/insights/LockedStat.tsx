import { Link } from "react-router";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";

/** 027: a statistic sold in the shop and not unlocked yet: its title, what it shows, the way to it. */
export function LockedStat({ name, icon, span }: { name: string; icon: string; span?: "full" | undefined }) {
  const t = useT();
  return (
    <AdminSection title={t(`media:insights.locked.${name}`)} icon={icon} span={span}>
      <div className="insights-locked">
        <Icon name="lock" size={28} />
        <p>{t("media:insights.locked.hint")}</p>
        <Link className="ds-button ds-button--secondary" to="/marketplace?type=statistic">
          <Icon name="shop" size={16} />
          {t("media:insights.locked.toShop")}
        </Link>
      </div>
    </AdminSection>
  );
}
