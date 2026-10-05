import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";

/** 027: only what the member owns is offered; the rest of the category is one line away, in the shop. */
export function InShop({ count, type }: { count: number; type: string }) {
  const t = useT();
  if (count <= 0) return null;
  return (
    <p className="in-shop">
      <Icon name="shop" size={16} />
      <span>{t("notifications:looks.available", { count })}</span>
      <Link to={`/marketplace?type=${type}`}>
        {t("notifications:looks.toShop")}
        <Icon name="chevron-right" size={14} />
      </Link>
    </p>
  );
}
