import { useMemo, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { InShop } from "../../appearance/InShop";
import "../../appearance/notification-looks.css";
import { type CatalogEntry, type Change, useCatalog } from "../api";
import { WidgetPreview } from "./WidgetPreview";

/**
 * Widget catalog (spec 009 T019; 027 redesign): only the widgets this member can add — permitted, enabled,
 * owned, allowed by policy — searchable, those not on the dashboard yet first, the ones already there
 * apart (a widget that may appear several times can be added again). Widgets sold in the shop are not
 * mixed in: one line says how many more the shop has, like the looks in Appearance. 027: a wide modal of
 * cards (the widget's look on top, what it shows and its sizes below) rather than a side drawer.
 */
export function CatalogDrawer({ apply }: { apply: (change: Change) => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const catalog = useCatalog(open);
  const entries = catalog.data ?? [];
  const inShop = entries.filter((e) => e.locked).length;
  const { toAdd, placed } = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = (e: CatalogEntry) =>
      !q ||
      t(e.widget.title_key).toLowerCase().includes(q) ||
      (e.widget.description_key ? t(e.widget.description_key).toLowerCase().includes(q) : false);
    const usable = entries
      .filter((e) => !e.locked && matches(e))
      .sort((a, b) => t(a.widget.title_key).localeCompare(t(b.widget.title_key)));
    return { toAdd: usable.filter((e) => !e.placed), placed: usable.filter((e) => e.placed) };
  }, [entries, query, t]);
  const card = (entry: CatalogEntry) => {
    const again = entry.placed && entry.widget.multiple;
    const done = entry.placed && !entry.widget.multiple;
    const title = t(entry.widget.title_key);
    return (
      <li key={entry.key} className="widget-gallery__item" data-placed={entry.placed || undefined}>
        <WidgetPreview
          className="widget-gallery__preview"
          widget={{
            key: entry.key,
            icon: entry.widget.icon,
            template: entry.widget.template,
            component_id: entry.widget.component_id,
          }}
        />
        <span className="widget-gallery__text">
          <strong>{title}</strong>
          {entry.widget.description_key ? <span>{t(entry.widget.description_key)}</span> : null}
          <span className="widget-gallery__size">
            <Icon name="maximize" size={11} />
            {t("dashboard:gallery.sizes", {
              min: `${entry.widget.min_w}×${entry.widget.min_h}`,
              max: `${entry.widget.max_w}×${entry.widget.max_h}`,
            })}
          </span>
        </span>
        {done ? (
          <span className="widget-gallery__added">
            <Icon name="check" size={14} />
            {t("dashboard:added")}
          </span>
        ) : (
          <Button
            variant={again ? "ghost" : "secondary"}
            aria-label={`${t(again ? "dashboard:catalogAgain" : "dashboard:add")} ${title}`}
            onClick={() => apply({ kind: "add", widget_key: entry.key })}
          >
            <Icon name="plus" size={14} />
            {t(again ? "dashboard:catalogAgain" : "dashboard:add")}
          </Button>
        )}
      </li>
    );
  };
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      size="lg"
      title={t("dashboard:catalog")}
      closeLabel={t("dashboard:done")}
      trigger={
        <Button variant="secondary">
          <Icon name="plus" size={18} />
          {t("dashboard:addWidget")}
        </Button>
      }
    >
      <div className="widget-catalog" data-modal>
        <label className="widget-catalog__search">
          <Icon name="search" size={16} />
          <span className="visually-hidden">{t("dashboard:catalogSearch")}</span>
          <input
            type="search"
            value={query}
            placeholder={t("dashboard:catalogSearch")}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <InShop count={inShop} type="widget" text={t("dashboard:catalogInShop", { count: inShop })} />
        {catalog.isPending ? <FunctionalState state="loading" /> : null}
        {catalog.isError ? <FunctionalState state="error" onRetry={() => catalog.refetch()} /> : null}
        {toAdd.length ? (
          <section aria-label={t("dashboard:catalogToAdd")}>
            <h3 className="widget-catalog__heading">
              {t("dashboard:catalogToAdd")} <span>{toAdd.length}</span>
            </h3>
            <ul className="dashboard-catalog widget-gallery">{toAdd.map(card)}</ul>
          </section>
        ) : null}
        {placed.length ? (
          <section aria-label={t("dashboard:catalogPlaced")}>
            <h3 className="widget-catalog__heading">
              {t("dashboard:catalogPlaced")} <span>{placed.length}</span>
            </h3>
            <ul className="dashboard-catalog widget-gallery">{placed.map(card)}</ul>
          </section>
        ) : null}
        {catalog.isSuccess && !toAdd.length && !placed.length ? (
          <p className="widget__meta">{t("dashboard:catalogNone")}</p>
        ) : null}
      </div>
    </Dialog>
  );
}
