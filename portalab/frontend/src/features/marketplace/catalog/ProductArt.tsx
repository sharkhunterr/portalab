import { type ReactNode, useEffect, useState } from "react";
import type { Ambient } from "../../../design-system/a11y/preferences";
import { LevelBadge } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { Notification } from "../../../design-system/components/Notification";
import { CelebrationScene } from "../../../design-system/feedback/Celebration";
import { AmbientLayer } from "../../../design-system/themes/AmbientLayer";
import { builtinTheme } from "../../../design-system/themes/builtin";
import { PALETTE_COLORS } from "../../../design-system/themes/palettes";
import { useT } from "../../../i18n/hooks/useT";
import { ThemeMiniature } from "../../appearance/AppearanceSettings";
import { useMe } from "../../auth/useAuth";
import { BannerArt, FramedAvatar, StyledName, WornBadge } from "../../community/profile/ProfileHero";
import { useCatalog } from "../../dashboard/api";
import { WidgetPreview } from "../../dashboard/catalog/WidgetPreview";
import { LevelUpPreview } from "../../gamification/levelup/LevelUpMoment";
import { type Product, useProducts } from "../api";
import { TYPE_ICONS } from "./ProductPoster";
import "../../appearance/notification-looks.css";
import "../product-art.css";

/** 027: a widget product shows the widget itself, in miniature, with the member's own data — a look for a
 * widget (#30) shows that widget wearing it. */
function WidgetArt({
  product,
  widget,
  config,
}: {
  product: Product;
  widget?: string | undefined;
  config?: Record<string, unknown> | undefined;
}) {
  const catalog = useCatalog(true);
  const key = widget ?? text(product.preview as Preview, "widget");
  const entry = (catalog.data ?? []).find((e) => e.key === key);
  return (
    <span className="product-art__widget product-art__widget--live">
      <WidgetPreview
        widget={{
          key: key ?? "",
          icon: entry?.widget.icon ?? product.icon,
          template: entry?.widget.template,
          component_id: entry?.widget.component_id,
          config_defaults: config,
        }}
      />
    </span>
  );
}

/**
 * A product's art (027): a small pre-rendering of what it is — a notification in that style or animation,
 * the banner, the framed avatar, the palette or theme colours, the badge or title as worn, a celebration,
 * a pack's contents — instead of a big icon; the icon stays for what cannot be drawn (features, plugins).
 * Inside the rarity frame: the type badge, and how many copies are left. Decoration only (``aria-hidden``):
 * the same facts are in the product's text.
 */
export type ArtSize = "card" | "sheet" | "mini";

export const TYPE_BADGE_ICON: Record<string, string> = {
  ...TYPE_ICONS,
  ambient: "snowflake",
  profile_background: "sparkles",
  name_style: "feather",
  bundle: "shop",
  notification_style: "bell",
  notification_animation: "sparkles",
  profile_banner: "image",
  avatar_frame: "user",
  profile_backdrop: "film",
  palette: "palette",
  level_badge: "star",
  level_up: "trophy",
};

type Preview = Record<string, unknown>;

function text(preview: Preview, field: string): string | undefined {
  return typeof preview[field] === "string" ? (preview[field] as string) : undefined;
}

/** Replays an entrance animation every few seconds (the CSS stops it under reduced motion). */
function useReplay(active: boolean, every = 2600): number {
  const [run, setRun] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setRun((n) => n + 1), every);
    return () => window.clearInterval(timer);
  }, [active, every]);
  return run;
}

function NotificationArt({
  style,
  animation,
  size,
}: {
  style?: string | undefined;
  animation?: string | undefined;
  size: ArtSize;
}) {
  const t = useT();
  const run = useReplay(Boolean(animation) && size !== "mini");
  return (
    <span
      key={run}
      className="ds-notifications product-art__notify"
      data-style={style ?? "toast"}
      data-animation={animation ?? "none"}
    >
      <Notification
        item={{
          id: "art",
          severity: "success",
          tone: "reward",
          title: t("notifications:looks.sampleTitle"),
          ...(size === "sheet" ? { body: t("notifications:looks.sampleBody") } : {}),
          badge: t("notifications:badge.reward"),
        }}
      />
    </span>
  );
}

const SWATCH_KEYS = ["dark-accent", "dark-alt", "light-accent", "light-alt"] as const;

function Swatches({ colors }: { colors: string[] }) {
  return (
    <span className="product-art__swatches">
      {SWATCH_KEYS.map((key, index) => (
        <span key={key} style={{ background: colors[index] }} />
      ))}
    </span>
  );
}

function PaletteArt({ palette, fallback }: { palette: string | undefined; fallback: ReactNode }) {
  const colors = PALETTE_COLORS[palette ?? ""];
  if (!colors) return fallback;
  const { dark, light } = colors;
  return (
    <span className="product-art__palette">
      <span className="product-art__ui" data-scheme="dark">
        <span style={{ background: dark.accent, color: dark.contrast }}>Aa</span>
        <span style={{ background: dark.accentAlt }} />
      </span>
      <span className="product-art__ui" data-scheme="light">
        <span style={{ background: light.accent, color: light.contrast }}>Aa</span>
        <span style={{ background: light.accentAlt }} />
      </span>
      <Swatches colors={[dark.accent, dark.accentAlt, light.accent, light.accentAlt]} />
    </span>
  );
}

function ThemeArt({ theme, fallback }: { theme: string | undefined; fallback: ReactNode }) {
  const definition = builtinTheme(theme ?? "");
  const c = definition?.colors;
  if (!c) return fallback;
  if (definition?.vocabulary || definition?.layout?.nav) {
    return (
      <span className="product-art__theme" style={{ background: c.surface, color: c.text }}>
        <ThemeMiniature theme={definition} />
        <span
          className="product-art__theme-name"
          style={{ fontFamily: definition.typography?.headingFamily, color: c.accent }}
        >
          {definition.name}
        </span>
      </span>
    );
  }
  return (
    <span className="product-art__app" style={{ background: c.surface, borderColor: c.border }}>
      <span className="product-art__app-bar" style={{ background: c.surfaceRaised }}>
        <span style={{ background: c.accent }} />
        <span style={{ background: c.textMuted }} />
      </span>
      <span className="product-art__app-body">
        <span className="product-art__app-nav" style={{ background: c.surfaceRaised }}>
          <span style={{ background: c.accent }} />
          <span style={{ background: c.textMuted }} />
          <span style={{ background: c.textMuted }} />
        </span>
        <span className="product-art__app-cards">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} style={{ background: c.surfaceRaised, borderColor: c.border }}>
              <span style={{ background: i % 2 ? (c.accentAlt ?? c.accent) : c.accent }} />
              <span style={{ background: c.text }} />
            </span>
          ))}
        </span>
      </span>
    </span>
  );
}

function CelebrationArt({ effect, size }: { effect: string | undefined; size: ArtSize }) {
  // 027: the real effect (the one played with the « +XP » bubble), replayed in the box
  const run = useReplay(size !== "mini", 2600);
  return (
    <span className="product-art__celebration">
      <CelebrationScene
        key={run}
        effect={effect ?? "sparkle"}
        event={{ kind: "reward", text: "+40 XP" }}
        contained
        reduced={size === "mini"}
      />
    </span>
  );
}

function PackArt({ keys, fallback }: { keys: string[]; fallback: ReactNode }) {
  const products = useProducts({ category: "", q: "" });
  const inner = keys
    .map((key) => (products.data ?? []).find((p) => p.key === key))
    .filter((p): p is Product => Boolean(p))
    .slice(0, 4);
  if (!inner.length) return fallback;
  return (
    <span className="product-art__pack" data-count={inner.length}>
      {inner.map((item) => (
        <ProductArt key={item.key} product={item} size="mini" />
      ))}
    </span>
  );
}

function ArtBody({ product, size, fallback }: { product: Product; size: ArtSize; fallback: ReactNode }) {
  const t = useT();
  const me = useMe();
  const preview = (product.preview ?? {}) as Preview;
  const name = me.data?.display_name ?? me.data?.login ?? "Portalab";
  switch (product.type) {
    case "notification_style":
      return <NotificationArt style={text(preview, "style")} size={size} />;
    case "notification_animation":
      return <NotificationArt animation={text(preview, "animation")} size={size} />;
    case "profile_banner":
      return (
        <span className="product-art__banner">
          <BannerArt banner={text(preview, "banner") ?? null} />
          {size !== "mini" ? (
            <FramedAvatar name={name} userId={me.data?.id} size={size === "sheet" ? "lg" : "md"} />
          ) : null}
        </span>
      );
    case "avatar_frame":
      return (
        <span className="product-art__frame">
          <FramedAvatar
            frame={text(preview, "frame")}
            name={name}
            userId={me.data?.id}
            size={size === "sheet" ? "xl" : size === "card" ? "lg" : "md"}
          />
        </span>
      );
    case "profile_backdrop":
      return (
        <span className="product-art__backdrop">
          <span className="product-art__film">
            {[0, 1, 2].map((i) => (
              <span key={i} />
            ))}
          </span>
          {size !== "mini" ? (
            <span className="product-art__caption">{t("marketplace:art.backdrop")}</span>
          ) : null}
        </span>
      );
    case "palette":
      return <PaletteArt palette={text(preview, "palette")} fallback={fallback} />;
    case "theme":
      return <ThemeArt theme={text(preview, "theme") ?? product.theme ?? undefined} fallback={fallback} />;
    case "bundle":
      return Array.isArray(preview.products) ? (
        <PackArt keys={preview.products as string[]} fallback={fallback} />
      ) : (
        fallback
      );
    case "badge":
      return (
        <span className="product-art__badge-worn" data-size={size}>
          <WornBadge
            kind="badge"
            item={{
              key: product.key,
              label: text(preview, "label") ?? product.name,
              icon: text(preview, "icon") ?? product.icon ?? "star",
              style: text(preview, "style") ?? null,
            }}
          />
        </span>
      );
    case "title":
      return (
        <span className="product-art__title">
          <span className="product-art__title-name">{name}</span>
          <WornBadge
            kind="title"
            item={{
              key: product.key,
              label: text(preview, "label") ?? product.name,
              style: text(preview, "style") ?? null,
            }}
          />
        </span>
      );
    case "level_badge":
      return (
        <span className="product-art__level" data-size={size}>
          {[7, 42, 253].map((level) => (
            <LevelBadge key={level} level={level} label={name} look={text(preview, "style")} />
          ))}
        </span>
      );
    case "level_up":
      return (
        <span className="product-art__levelup" data-size={size}>
          <LevelUpPreview look={text(preview, "animation") || "classic"} label={name} size={size} />
        </span>
      );
    case "name_style":
      return (
        <span className="product-art__name" data-size={size}>
          <StyledName name={name} style={text(preview, "style")} />
        </span>
      );
    case "ambient":
    case "profile_background":
      return (
        <span className="product-art__ambient">
          <AmbientLayer
            kind={(text(preview, "ambient") ?? text(preview, "background") ?? "none") as Ambient}
            contained
          />
          {size !== "mini" && product.type === "profile_background" ? (
            <FramedAvatar name={name} userId={me.data?.id} size={size === "sheet" ? "lg" : "md"} />
          ) : null}
        </span>
      );
    case "effect":
      return <CelebrationArt effect={text(preview, "effect")} size={size} />;
    case "widget_option": {
      const option = text(preview, "option") ?? "";
      const [widget, setting] = option.split(":");
      // 027 (#30): a look for a widget — the widget itself, wearing it
      const look = setting?.startsWith("style=") ? setting.slice("style=".length) : null;
      if (look && widget) return <WidgetArt product={product} widget={widget} config={{ style: look }} />;
      return (
        <span className="product-art__widget product-art__option">
          <span className="product-art__widget-head">
            <Icon name="settings" size={14} />
            <span />
          </span>
          <strong>{setting?.replace("=", " · ") ?? option}</strong>
          <span className="product-art__caption">{widget}</span>
        </span>
      );
    }
    case "statistic":
      return (
        <span className="product-art__widget product-art__stat">
          <span className="product-art__stat-bars">
            {["s1", "s2", "s3", "s4", "s5"].map((key) => (
              <span key={key} />
            ))}
          </span>
        </span>
      );
    case "project_launch":
      return (
        <span className="product-art__launch">
          <Icon name="lightbulb" size={size === "sheet" ? 56 : 34} />
          <span className="product-art__caption">{t("marketplace:art.launch")}</span>
        </span>
      );
    case "quota":
      return (
        <span className="product-art__quota">
          <strong>+{String(preview.units ?? "")}</strong>
          <span>{t("marketplace:art.requests")}</span>
        </span>
      );
    case "widget":
      return <WidgetArt product={product} />;
    default:
      return fallback; // what cannot be drawn (features, plugins, access…) keeps its icon
  }
}

export function ProductArt({ product, size = "card" }: { product: Product; size?: ArtSize }) {
  const t = useT();
  const icon = product.icon ?? TYPE_ICONS[product.type] ?? "shop";
  const fallback = (
    <span className="product-art__icon">
      <Icon name={icon} size={size === "sheet" ? 64 : size === "mini" ? 22 : 40} />
    </span>
  );
  const left = product.remaining;
  return (
    <span
      className="product-poster product-art"
      data-rarity={product.rarity ?? "common"}
      data-size={size}
      data-kind={product.type}
      aria-hidden="true"
    >
      <span className="product-poster__glow" />
      <span className="product-art__stage">
        <ArtBody product={product} size={size} fallback={fallback} />
      </span>
      {size !== "mini" ? (
        <>
          <span className="product-art__type">
            <Icon name={TYPE_BADGE_ICON[product.type] ?? "shop"} size={12} />
            {t(`marketplace:type.${product.type}`)}
          </span>
          {product.owned ? (
            <span className="product-art__acquired">
              <Icon name="check" size={12} />
              {t("marketplace:product.owned")}
            </span>
          ) : left !== null && left !== undefined ? (
            <span className="product-art__stock" data-out={left === 0 || undefined}>
              {left === 0 ? t("marketplace:stock.soldOut") : t("marketplace:stock.left", { count: left })}
            </span>
          ) : null}
        </>
      ) : null}
    </span>
  );
}
