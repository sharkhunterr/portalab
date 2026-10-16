import { useState } from "react";
import { Link } from "react-router";
import { AdminPage, AdminSection, SearchBox, StatusBadge } from "../../design-system/admin/AdminKit";
import { Icon } from "../../design-system/components/Icon";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { useCatalog } from "../dashboard/api";
import { type PackRow, type PackWidgetElement, useVisualPacks } from "./api";
import { nameOf } from "./parts";
import { VisualPackImport } from "./VisualPackImport";
import "./visuals.css";

/**
 * 028: Extensions → « Widgets » — what the visual packs bring for the dashboard. Its import first (a widget
 * pack is a visual pack), then each pack's elements as small cards — a new widget, a widget's look, an option
 * (shown otherwise, drawn over it, its look) or a value of a pack widget's own setting — each saying the
 * widget it is for, the data it reads, and whether it is sold or offered. Filtered by kind, searchable.
 */

type Kind = "widget" | "style" | "option";
const KIND_ICON: Record<string, string> = {
  widget: "dashboard",
  style: "palette",
  value: "settings",
  replace: "layers",
  overlay: "sparkles",
  addon: "sparkles",
};

function kindOf(element: PackWidgetElement): string {
  if (element.type === "widget") return "widget";
  if (element.type === "widget_style") return "style";
  if (element.widget?.setting) return "value";
  if (element.widget?.place === "replace") return "replace";
  if (element.widget?.place === "overlay") return "overlay";
  return "addon";
}
const familyOf = (kind: string): Kind =>
  kind === "widget" ? "widget" : kind === "style" ? "style" : "option";

export default function WidgetPacksAdmin() {
  const t = useT();
  const packs = useVisualPacks();
  const catalog = useCatalog(true);
  const language = useLocaleContext().language.split("-")[0] ?? "en";
  const [family, setFamily] = useState<Kind | "all">("all");
  const [query, setQuery] = useState("");
  const titles = Object.fromEntries((catalog.data ?? []).map((e) => [e.key, t(e.widget.title_key)]));
  const q = query.trim().toLowerCase();
  const keep = (element: PackWidgetElement) =>
    (family === "all" || familyOf(kindOf(element)) === family) &&
    (!q || nameOf(element.names, element.product, language).toLowerCase().includes(q));
  const bringing = (packs.data?.packs ?? [])
    .map((pack) => ({ pack, elements: (pack.widgets ?? []).filter(keep) }))
    .filter((entry) => entry.elements.length);
  const counts = { all: 0, widget: 0, style: 0, option: 0 };
  for (const pack of packs.data?.packs ?? [])
    for (const element of pack.widgets ?? []) {
      counts.all += 1;
      counts[familyOf(kindOf(element))] += 1;
    }
  return (
    <AdminPage
      icon="dashboard"
      title={t("admin:widgetPacks.title")}
      description={t("admin:widgetPacks.description")}
      secondary={
        <Link className="ds-button ds-button--ghost" to="/admin/dashboard">
          <Icon name="dashboard" size={16} /> {t("admin:widgetPacks.dashboard")}
        </Link>
      }
      wide
    >
      <VisualPackImport widgets />
      <AdminSection title={t("admin:widgetPacks.fromPacks")} icon="package" flush>
        <div className="vp-toolbar">
          <fieldset className="vp-tabs">
            <legend className="visually-hidden">{t("admin:widgetPacks.what")}</legend>
            {(["all", "widget", "style", "option"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={family === value}
                onClick={() => setFamily(value)}
              >
                {t(`admin:widgetPacks.family.${value}`)}
                <span className="vp-tabs__count">{counts[value]}</span>
              </button>
            ))}
          </fieldset>
          <SearchBox label={t("admin:widgetPacks.search")} value={query} onChange={setQuery} />
        </div>
        {packs.isPending ? <FunctionalState state="loading" label={t("admin:visuals.loading")} /> : null}
        {packs.isError ? <FunctionalState state="error" onRetry={() => packs.refetch()} /> : null}
        {packs.isSuccess && !bringing.length ? (
          <p className="visuals-empty">
            {t(counts.all ? "admin:widgetPacks.noMatch" : "admin:widgetPacks.none")}
          </p>
        ) : null}
        {bringing.map(({ pack, elements }) => (
          <PackGroup key={pack.id} pack={pack} elements={elements} titles={titles} language={language} />
        ))}
      </AdminSection>
    </AdminPage>
  );
}

function PackGroup({
  pack,
  elements,
  titles,
  language,
}: {
  pack: PackRow;
  elements: PackWidgetElement[];
  titles: Record<string, string>;
  language: string;
}) {
  const t = useT();
  const version = pack.current ?? pack.versions[0]?.version;
  const live = pack.state === "enabled" && Boolean(pack.current);
  return (
    <section className="wp-group" aria-label={nameOf(pack.names, pack.id, language)}>
      <header className="wp-group__head">
        <strong>{nameOf(pack.names, pack.id, language)}</strong>
        <StatusBadge tone={live ? "ok" : "neutral"}>
          {live ? t("admin:widgetPacks.live", { version: pack.current ?? "" }) : t("admin:widgetPacks.off")}
        </StatusBadge>
        {version ? (
          <Link className="wp-group__review" to={`/admin/visuals/${pack.id}/${version}?step=review`}>
            <Icon name="coins" size={14} /> {t("admin:widgetPacks.review")}
          </Link>
        ) : null}
      </header>
      <ul className="wp-cards">
        {elements.map((element) => (
          <Card key={element.product} element={element} titles={titles} language={language} />
        ))}
      </ul>
    </section>
  );
}

function Card({
  element,
  titles,
  language,
}: {
  element: PackWidgetElement;
  titles: Record<string, string>;
  language: string;
}) {
  const t = useT();
  const kind = kindOf(element);
  const target = element.widget?.for;
  const widgetName = (key: string) =>
    titles[key] ?? (key.startsWith("pack.") ? t(`dashboard:packWidget.${key.slice(5)}`) : key);
  const reads = element.contracts.map((c) =>
    c.startsWith("widget:") ? widgetName(c.slice(7)) : t(`dashboard:contract.${c}`),
  );
  return (
    <li className="wp-card" data-kind={kind}>
      <div className="wp-card__head">
        <span className="wp-card__icon" aria-hidden="true">
          <Icon name={KIND_ICON[kind] ?? "sparkles"} size={16} />
        </span>
        <span className="wp-card__title">
          <strong>{nameOf(element.names, element.product, language)}</strong>
          <span>
            {t(`admin:widgetPacks.kind.${kind}`)}
            {element.widget?.setting ? ` · ${element.widget.value}` : ""}
          </span>
        </span>
      </div>
      {element.type !== "widget" ? (
        <p className="wp-card__line">
          <Icon name="target" size={13} />
          {target ? widgetName(target) : t("admin:widgetPacks.every")}
        </p>
      ) : null}
      {reads.length ? (
        <p className="wp-card__line">
          <Icon name="shield" size={13} />
          {reads.join(", ")}
        </p>
      ) : null}
      <p className="wp-card__price" data-given={!element.sold || undefined}>
        {element.sold
          ? element.price === null
            ? t("admin:visuals.review.rewardOnly")
            : t("admin:widgetPacks.sold", {
                price: element.price,
                rarity: t(`marketplace:rarity.${element.rarity}`),
              })
          : t("admin:visuals.review.given")}
      </p>
    </li>
  );
}
