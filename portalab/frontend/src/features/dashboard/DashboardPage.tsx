import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { api } from "../../api/client";
import { connectStream } from "../../api/stream";
import { useAnnounce } from "../../design-system/a11y/Announce";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useDeviceClass } from "../../design-system/components/Layout";
import { PageHeader } from "../../design-system/components/PageHeader";
import { EmptyState } from "../../design-system/components/Placeholders";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useMe } from "../auth/useAuth";
import { IncidentBanner } from "../support/incidents/IncidentBanner";
import { type Change, DASHBOARD_KEY, useDashboard, useDashboardWrite } from "./api";
import { CatalogDrawer } from "./catalog/CatalogDrawer";
import { EditControls } from "./edit/EditControls";
import { itemsOf, keyOf, useEditSession } from "./edit/EditSession";
import { WidgetFrame } from "./frame/WidgetFrame";
import { DashboardGrid } from "./grid/DashboardGrid";
import { readingOrder } from "./grid/engine";
import { SinceLastLoginCard } from "./summary/SinceLastLoginCard";
import { WelcomeCard } from "./WelcomeCard";
import "./widgets/builtin";
import "./widgets/media";
import "../gamification/widget";
import "../community/widget";
import "../marketplace/widget";
import { ActiveCampaignBanner } from "../campaigns/banner/ActiveCampaignBanner";

const ONBOARDED = "portalab.onboarding.dashboard";

/**
 * Home dashboard (spec 009 T012/T019): the effective dashboard (policy applied server-side), each widget in
 * its own isolated frame; "Customize" turns on keyboard/touch edit controls and the catalog; live
 * ``widget.invalidate`` messages refetch only the affected widget (refetch re-authorizes).
 */
/** Greeting by time of day (027 FR-027). */
export function greetingKey(hour: number): string {
  if (hour < 5) return "dashboard:greeting.night";
  if (hour < 12) return "dashboard:greeting.morning";
  if (hour < 18) return "dashboard:greeting.afternoon";
  return "dashboard:greeting.evening";
}

export function DashboardPage({ live = true }: { live?: boolean }) {
  const t = useT();
  const format = useFormat();
  const me = useMe();
  const name = me.data?.display_name ?? me.data?.login ?? "";
  const headingId = useId();
  const announce = useAnnounce();
  const client = useQueryClient();
  const dashboard = useDashboard();
  const device = useDeviceClass();
  const desktop = device === "desktop";
  const columns = desktop ? 12 : device === "tablet" ? 6 : 2;
  const [editing, setEditing] = useState(false); // tablet/phone edit mode (027 FR-046)
  const write = useDashboardWrite(() => announce(t("dashboard:conflict")));
  const apply = (change: Change) => write.mutate(change);

  useEffect(() => {
    if (!live) return;
    const handle = connectStream({
      topics: ["widget.invalidate"],
      onEvent: (event) => {
        const key = (event.data as { widget?: string } | null)?.widget;
        if (key) void client.invalidateQueries({ queryKey: ["widget", key] });
      },
    });
    return () => handle.close();
  }, [live, client]);

  const loaded = dashboard.isSuccess;
  useEffect(() => {
    // the starter dashboard exists once the dashboard is shown: the onboarding "dashboard" step is done (002)
    if (!loaded) return;
    try {
      if (window.sessionStorage.getItem(ONBOARDED)) return;
      window.sessionStorage.setItem(ONBOARDED, "1");
    } catch {
      // no storage: completing twice is harmless (idempotent server side)
    }
    void api
      .POST("/api/v1/me/onboarding/{step}/complete", { params: { path: { step: "dashboard" } } })
      .catch(() => undefined);
  }, [loaded]);

  const instances = dashboard.data?.instances ?? [];
  const visible = instances.filter((i) => i.status === "active");
  const hidden = instances.filter((i) => i.status === "hidden");
  // desktop: a 2D edit session (drag, resize, keyboard) saved in one write (027 US6)
  const session = useEditSession(visible, dashboard.data?.layout_version, () => {
    void client.invalidateQueries({ queryKey: DASHBOARD_KEY });
  });
  const arranging = desktop && session.editing;
  const isEditing = desktop ? session.editing : editing;
  const cells = session.draft ?? new Map(visible.map((i) => [keyOf(i), { x: i.x, y: i.y, w: i.w, h: i.h }]));
  const order = readingOrder(itemsOf(cells, visible));
  const arrangeOf = (key: string) => {
    if (!arranging) return undefined;
    const index = order.findIndex((item) => item.id === key);
    const cell = order[index];
    if (!cell) return undefined;
    return {
      cell,
      index,
      count: order.length,
      prev: order[index - 1],
      next: order[index + 1],
      move: (x: number, y: number) => session.move(key, x, y),
      resize: (w: number, h: number) => session.resize(key, w, h),
    };
  };
  return (
    <div className="dashboard-page">
      <PageHeader
        title={name ? t(greetingKey(new Date().getHours()), { name }) : t("dashboard:title")}
        context={
          <>
            <span className="dashboard-page__date">{format.date(new Date(), "long")}</span>
            {" · "}
            {t("dashboard:subtitle")}
          </>
        }
        secondary={
          arranging ? (
            <>
              <CatalogDrawer apply={apply} />
              <Button variant="secondary" disabled={session.saving} onClick={() => void session.cancel()}>
                {t("dashboard:cancel")}
              </Button>
              <Button disabled={session.saving} onClick={() => void session.save()}>
                <Icon name="check" size={18} />
                {t("dashboard:save")}
              </Button>
            </>
          ) : (
            <>
              {editing ? <CatalogDrawer apply={apply} /> : null}
              <Button
                variant={editing ? "primary" : "secondary"}
                aria-pressed={editing}
                onClick={() => (desktop ? session.start() : setEditing((value) => !value))}
              >
                <Icon name={editing ? "check" : "dashboard"} size={18} />
                {editing ? t("dashboard:done") : t("dashboard:edit")}
              </Button>
            </>
          )
        }
      />
      <WelcomeCard />
      <ActiveCampaignBanner />
      <IncidentBanner />
      <SinceLastLoginCard />
      {dashboard.isPending ? <FunctionalState state="loading" /> : null}
      {dashboard.isError ? <FunctionalState state="error" onRetry={() => dashboard.refetch()} /> : null}
      {dashboard.data && visible.length === 0 ? (
        <EmptyState
          icon="dashboard"
          title={t("dashboard:empty")}
          message={t("dashboard:emptyHint")}
          action={{ label: t("dashboard:addWidget"), onSelect: () => setEditing(true) }}
        />
      ) : null}
      <h2 id={headingId} className="visually-hidden">
        {t("dashboard:title")}
      </h2>
      {arranging ? <p className="dashboard-page__hint">{t("dashboard:editHint")}</p> : null}
      <DashboardGrid
        label={t("dashboard:title")}
        instances={visible}
        cells={cells}
        columns={columns}
        arranger={arranging ? session : null}
        render={(instance, handles) => (
          <WidgetFrame
            instance={instance}
            handles={handles}
            controls={
              isEditing ? (
                <EditControls
                  instance={instance}
                  count={instances.length}
                  apply={apply}
                  arrange={arrangeOf(keyOf(instance))}
                />
              ) : null
            }
          />
        )}
      />
      {isEditing && hidden.length ? (
        <section className="ds-panel" aria-label={t("dashboard:hidden")}>
          <h3>{t("dashboard:hidden")}</h3>
          <ul className="widget-list">
            {hidden.map((instance) => (
              <li key={instance.id ?? instance.widget_key}>
                {instance.widget ? t(instance.widget.title_key) : instance.widget_key}{" "}
                <Button
                  variant="secondary"
                  onClick={() =>
                    instance.id && apply({ kind: "patch", id: instance.id, body: { status: "active" } })
                  }
                >
                  {t("dashboard:show")}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

export default DashboardPage;
export { DASHBOARD_KEY };
