import { Link } from "react-router";
import { useT } from "../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";

interface Featured {
  key: string;
  name: string;
  type: string;
  price: number | null;
}

/** Dashboard widget ``marketplace.featured`` (spec 015 T033): a few available products. */
function FeaturedWidget({ payload }: WidgetProps) {
  const t = useT();
  const items = ((payload.data ?? {}) as { items?: Featured[] }).items ?? [];
  return (
    <ul className="widget-list">
      {items.map((item) => (
        <li key={item.key}>
          <Link to={`/marketplace/products/${item.key}`}>{item.name}</Link> ·{" "}
          {item.price
            ? t("marketplace:purchase.price", { price: item.price })
            : t("marketplace:purchase.free")}
        </li>
      ))}
    </ul>
  );
}

registerWidgetComponent("marketplace.featured", FeaturedWidget);
