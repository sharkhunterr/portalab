import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { CoinBadge } from "../../../design-system/components/Badges";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Notification } from "../../../design-system/components/Notification";
import { Dialog } from "../../../design-system/components/Overlays";
import { builtinTheme } from "../../../design-system/themes/builtin";
import { PALETTE_COLORS } from "../../../design-system/themes/palettes";
import { useT } from "../../../i18n/hooks/useT";
import { useMe } from "../../auth/useAuth";
import { useHasPermission } from "../../authz/useMyPermissions";
import { BannerArt, FramedAvatar } from "../../community/profile/ProfileHero";
import { type Product, useProduct } from "../api";
import { ConditionsChecklist } from "../product/ConditionsChecklist";
import { PurchaseDialog } from "../product/PurchaseDialog";
import { ProductPoster } from "./ProductPoster";
import "../../appearance/notification-looks.css";

/**
 * A product opened from the shop (027): its poster, name, type, rarity, description and price, a live
 * preview when the type has one (a notification in that style or animation, the banner, the framed avatar,
 * the palette or theme colours, a pack's contents), its conditions, and buying it — without leaving the
 * shelves. The full page stays one link away.
 */
function NotificationSample({
  style,
  animation,
}: {
  style?: string | undefined;
  animation?: string | undefined;
}) {
  const t = useT();
  const [run, setRun] = useState(0);
  return (
    <div className="product-preview__notify">
      <div
        key={run}
        className="ds-notifications product-preview__stage"
        data-style={style ?? "toast"}
        data-animation={animation ?? "slide"}
      >
        <Notification
          item={{
            id: "preview",
            severity: "success",
            tone: "reward",
            title: t("notifications:looks.sampleTitle"),
            body: t("notifications:looks.sampleBody"),
            badge: t("notifications:badge.reward"),
          }}
        />
      </div>
      {animation ? (
        <Button variant="secondary" onClick={() => setRun((n) => n + 1)}>
          <Icon name="sync" size={14} />
          {t("marketplace:preview.replay")}
        </Button>
      ) : null}
    </div>
  );
}

function Swatches({ colors }: { colors: string[] }) {
  return (
    <span className="product-preview__swatches" aria-hidden="true">
      {colors.map((color) => (
        <span key={color} style={{ background: color }} />
      ))}
    </span>
  );
}

function PackContents({ keys }: { keys: string[] }) {
  const t = useT();
  const client = useQueryClient();
  const known = client
    .getQueriesData<Product[]>({ queryKey: ["marketplace", "products"] })
    .flatMap(([, data]) => data ?? []);
  return (
    <div className="ds-stack">
      <strong>{t("marketplace:shop.packContains")}</strong>
      <ul className="product-preview__pack">
        {keys.map((key) => {
          const item = known.find((p) => p.key === key);
          return (
            <li key={key} data-rarity={item?.rarity ?? "common"}>
              {item ? <ProductPoster product={item} /> : <Icon name="shop" />}
              <span>
                {item?.name ?? key}
                {item ? <span className="admin-muted">{t(`marketplace:type.${item.type}`)}</span> : null}
              </span>
              {item?.owned ? <Icon name="check" size={16} label={t("marketplace:product.owned")} /> : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Preview({ product }: { product: Product }) {
  const t = useT();
  const me = useMe();
  const preview = (product.preview ?? {}) as Record<string, unknown>;
  const text = (field: string) =>
    typeof preview[field] === "string" ? (preview[field] as string) : undefined;
  const name = me.data?.display_name ?? me.data?.login ?? "?";
  switch (product.type) {
    case "notification_style":
      return <NotificationSample style={text("style")} />;
    case "notification_animation":
      return <NotificationSample animation={text("animation")} />;
    case "profile_banner":
      return (
        <div className="product-preview__banner">
          <BannerArt banner={text("banner") ?? null} />
        </div>
      );
    case "avatar_frame":
      return (
        <div className="product-preview__frame">
          <FramedAvatar frame={text("frame")} name={name} userId={me.data?.id} size="xl" />
        </div>
      );
    case "profile_backdrop":
      return (
        <div className="product-preview__banner product-preview__banner--backdrop">
          <BannerArt banner="starfield" />
          <span className="product-preview__overlay">
            <Icon name="film" size={28} />
            {t("marketplace:preview.backdrop")}
          </span>
        </div>
      );
    case "palette": {
      const colors = PALETTE_COLORS[text("palette") ?? ""];
      return colors ? (
        <div className="product-preview__palette">
          <Swatches colors={[colors.dark.accent, colors.dark.accentAlt]} />
          <Swatches colors={[colors.light.accent, colors.light.accentAlt]} />
        </div>
      ) : null;
    }
    case "theme": {
      const theme = builtinTheme(text("theme") ?? product.theme ?? "");
      const c = theme?.colors;
      return c ? (
        <div
          className="product-preview__theme"
          style={{ background: c.surface, color: c.text, borderColor: c.border }}
          aria-hidden="true"
        >
          <span style={{ background: c.surfaceRaised }}>
            <span style={{ background: c.accent }} />
            <span style={{ background: c.textMuted }} />
          </span>
          <Swatches colors={[c.accent, c.accentAlt ?? c.accent, c.surfaceRaised, c.text]} />
        </div>
      ) : null;
    }
    case "bundle":
      return Array.isArray(preview.products) ? <PackContents keys={preview.products as string[]} /> : null;
    case "badge":
    case "title":
      return text("label") ? (
        <span className="product-preview__badge">
          <Icon name={text("icon") ?? (product.type === "title" ? "trophy" : "star")} size={18} />
          {text("label")}
        </span>
      ) : null;
    default:
      return null;
  }
}

export function ProductModal({ product, onClose }: { product: Product; onClose: () => void }) {
  const t = useT();
  const full = useProduct(product.key);
  const data = full.data ?? product;
  const canBuy = useHasPermission("marketplace.purchase");
  const [buying, setBuying] = useState(false);
  const rarity = data.rarity ?? "common";
  const description = Object.values(data.descriptions)[0];
  const eligible = (data.eligibility ?? []).every((c) => c.met);
  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      size="lg"
      title={data.name}
      closeLabel={t("marketplace:purchase.close")}
      trigger={<span hidden />}
    >
      <div className="product-modal" data-rarity={rarity}>
        <ProductPoster product={data} size="lg" />
        <div className="product-modal__text">
          <span className="product-card__rarity">
            {t(`marketplace:rarity.${rarity}`)} · {t(`marketplace:type.${data.type}`)}
          </span>
          {description ? <p>{description}</p> : null}
          <div className="ds-stack--row">
            {data.owned ? (
              <span className="product-card__owned">
                <Icon name="check" size={16} /> {t("marketplace:product.owned")}
              </span>
            ) : data.price_coins ? (
              <CoinBadge amount={data.price_coins} label={t("gamification:value.coins")} />
            ) : (
              <span className="ds-badge">{t("marketplace:purchase.free")}</span>
            )}
          </div>
        </div>
      </div>
      <section className="product-preview" aria-label={t("marketplace:preview.title")}>
        <Preview product={data} />
      </section>
      {data.eligibility?.length ? <ConditionsChecklist checks={data.eligibility} /> : null}
      <div className="ds-stack--row product-modal__actions">
        {!data.owned && canBuy && data.state === "available" && !buying ? (
          <Button onClick={() => setBuying(true)} disabled={!eligible}>
            <Icon name="coins" size={16} />
            {t("marketplace:product.acquire")}
          </Button>
        ) : null}
        <Link to={`/marketplace/products/${data.key}`} onClick={onClose}>
          {t("marketplace:preview.details")}
        </Link>
      </div>
      {buying ? <PurchaseDialog product={data} onClose={() => setBuying(false)} /> : null}
    </Dialog>
  );
}
