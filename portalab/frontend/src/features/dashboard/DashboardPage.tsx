import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { Link } from "react-router";
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
import { useHasPermission } from "../authz/useMyPermissions";
import { type Change, DASHBOARD_KEY, type Instance, useDashboard, useDashboardWrite } from "./api";
import { CatalogDrawer } from "./catalog/CatalogDrawer";
import { EditControls } from "./edit/EditControls";
import { cellsFor, type LayoutMode, useEditSession } from "./edit/EditSession";
import { EmptyWidgets } from "./frame/emptiness";
import { WidgetFrame } from "./frame/WidgetFrame";
import { DashboardGrid } from "./grid/DashboardGrid";
import { VIEW_COLUMNS, type View } from "./grid/engine";
import "./summary/SinceLastLoginCard";
import "./widgets/tiles";
import "./widgets/layout";
import { WelcomeCard } from "./WelcomeCard";
import "./widgets/builtin";
import "./widgets/media";
import "./widgets/calendar";
import "../gamification/widget";
import "../community/widget";
import "../marketplace/widget";
import "../support/incidents/widget";
import "../support/tickets/widget";
import "../campaigns/widget";
import "./widgets/discover";
import "./widgets/skins"; // 027 (#31): last — the other looks wrap the widgets registered above

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

const VIEWS: Array<{ view: View; icon: string }> = [
  { view: "desktop", icon: "monitor" },
  { view: "tablet", icon: "tablet" },
  { view: "phone", icon: "smartphone" },
];

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
  const deviceView: View = device === "desktop" ? "desktop" : device === "tablet" ? "tablet" : "phone";
  const write = useDashboardWrite(() => announce(t("dashboard:conflict")));
  const apply = (change: Change) => write.mutate(change);
  const mode: LayoutMode = dashboard.data?.layout_mode === "per_device" ? "per_device" : "shared";

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

  const instances = useMemo(() => dashboard.data?.instances ?? [], [dashboard.data]);
  const visible = useMemo(() => instances.filter((i) => i.status === "active"), [instances]);
  const hidden = instances.filter((i) => i.status === "hidden");
  // a 2D edit session (drag, resize, keyboard, auto fit) of one screen, saved in one write (027 US6)
  const session = useEditSession(visible, dashboard.data?.layout_version, mode, () => {
    void client.invalidateQueries({ queryKey: DASHBOARD_KEY });
  });
  const arranging = session.editing;
  // 027: widgets set to « hide when empty » that have nothing to show right now
  const [emptyWidgets, setEmptyWidgets] = useState<ReadonlySet<string>>(new Set());
  const reportEmpty = useCallback((key: string, empty: boolean) => {
    setEmptyWidgets((current) => {
      if (current.has(key) === empty) return current;
      const next = new Set(current);
      if (empty) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);
  const isEditing = arranging;
  const shownView: View = arranging ? session.view : deviceView;
  const columns = VIEW_COLUMNS[shownView];
  const cells = session.draft ?? cellsFor(visible, shownView, mode);
  const fresh = async () => {
    await client.refetchQueries({ queryKey: DASHBOARD_KEY });
    return (client.getQueryData<{ instances?: Instance[] }>(DASHBOARD_KEY)?.instances ?? []).filter(
      (i) => i.status === "active",
    );
  };
  const switchView = async (view: View) => {
    if (view === session.view) return;
    if (session.dirty) await session.save();
    session.start(view, await fresh());
  };
  /**
   * Save the arrangement. A phone or tablet arranged while the layout is shared gets its own layout first
   * (027): the other screens keep what they showed, this one keeps what was just arranged.
   */
  const save = async () => {
    if (mode === "shared" && session.view !== "desktop") {
      await fresh();
      const before = client.getQueryData<{ layout_version?: number }>(DASHBOARD_KEY)?.layout_version;
      await api.PUT("/api/v1/dashboard/layout-mode", {
        body: { mode: "per_device" },
        ...(before !== undefined ? { headers: { "If-Match": String(before) } } : {}),
      });
      await fresh();
      announce(t("dashboard:layoutMode.per_device.done"));
      await session.save(client.getQueryData<{ layout_version?: number }>(DASHBOARD_KEY)?.layout_version);
      return;
    }
    await session.save();
  };
  /** 027: back to the default dashboard (asks first: my arrangement and widgets are replaced). */
  const canManage = useHasPermission("dashboard.manage");
  const restoreDefault = async () => {
    if (!window.confirm(t("dashboard:defaultConfirm"))) return;
    await session.cancel();
    await api.POST("/api/v1/dashboard/reset", {});
    await fresh();
    announce(t("dashboard:defaultDone"));
  };
  const switchMode = async (next: LayoutMode) => {
    if (session.dirty) await session.save();
    await fresh();
    const version = client.getQueryData<{ layout_version?: number }>(DASHBOARD_KEY);
    await api.PUT("/api/v1/dashboard/layout-mode", {
      body: { mode: next },
      ...(version?.layout_version !== undefined
        ? { headers: { "If-Match": String(version.layout_version) } }
        : {}),
    });
    const instancesNow = await fresh();
    announce(t(`dashboard:layoutMode.${next}.done`));
    if (arranging) session.start(next === "shared" ? "desktop" : session.view, instancesNow, next);
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
              <Button disabled={session.saving} onClick={() => void save()}>
                <Icon name="check" size={18} />
                {t("dashboard:save")}
              </Button>
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={() => session.start(deviceView)}>
                <Icon name="dashboard" size={18} />
                {t("dashboard:edit")}
              </Button>
            </>
          )
        }
      />
      <WelcomeCard />
      {dashboard.isPending ? <FunctionalState state="loading" /> : null}
      {dashboard.isError ? <FunctionalState state="error" onRetry={() => dashboard.refetch()} /> : null}
      {dashboard.data && visible.length === 0 ? (
        <EmptyState
          icon="dashboard"
          title={t("dashboard:empty")}
          message={t("dashboard:emptyHint")}
          action={{ label: t("dashboard:addWidget"), onSelect: () => session.start(deviceView) }}
        />
      ) : null}
      <h2 id={headingId} className="visually-hidden">
        {t("dashboard:title")}
      </h2>
      {isEditing ? (
        <section className="dashboard-toolbar" aria-label={t("dashboard:toolbar")}>
          <fieldset className="ds-subnav" aria-label={t("dashboard:screens")}>
            {VIEWS.map(({ view, icon }) => (
              <button
                key={view}
                type="button"
                aria-pressed={shownView === view}
                disabled={
                  !arranging ||
                  (deviceView === "desktop" ? mode === "shared" && view !== "desktop" : view !== deviceView)
                }
                title={mode === "shared" && view !== "desktop" ? t("dashboard:sharedHint") : undefined}
                onClick={() => void switchView(view)}
              >
                <Icon name={icon} size={16} />
                {t(`dashboard:view.${view}`)}
              </button>
            ))}
          </fieldset>
          <label className="dashboard-toolbar__mode">
            <input
              type="checkbox"
              role="switch"
              aria-checked={mode === "per_device"}
              checked={mode === "per_device"}
              onChange={(event) => void switchMode(event.target.checked ? "per_device" : "shared")}
            />
            <span>
              <strong>{t("dashboard:layoutMode.label")}</strong>
              <span>{t(`dashboard:layoutMode.${mode}.hint`)}</span>
            </span>
          </label>
          {arranging ? (
            <Button variant="secondary" onClick={() => session.autofit()}>
              <Icon name="maximize" size={16} />
              {t("dashboard:autofit")}
            </Button>
          ) : null}
          {arranging ? (
            <Button variant="ghost" disabled={session.saving} onClick={() => void restoreDefault()}>
              <Icon name="sync" size={16} />
              {t("dashboard:default")}
            </Button>
          ) : null}
          {arranging && canManage ? (
            // 027: where the widgets imposed on every member (pinned, required, locked…) are set
            <Link className="ds-button ds-button--ghost" to="/admin/dashboard">
              <Icon name="lock" size={16} />
              {t("dashboard:membersWidgets")}
            </Link>
          ) : null}
          <p className="dashboard-page__hint">
            {t("dashboard:editHint")}
            {mode === "shared" && deviceView !== "desktop" ? ` ${t("dashboard:ownLayoutOnSave")}` : ""}
          </p>
        </section>
      ) : null}
      <div
        className="dashboard-stage"
        data-view={shownView}
        data-preview={shownView !== deviceView || undefined}
      >
        <EmptyWidgets.Provider value={reportEmpty}>
          <DashboardGrid
            label={t("dashboard:title")}
            instances={visible}
            cells={cells}
            columns={columns}
            arranger={arranging ? session : null}
            collapsed={emptyWidgets}
            render={(instance, handles) => (
              <WidgetFrame
                instance={instance}
                handles={handles}
                controls={isEditing ? <EditControls instance={instance} apply={apply} /> : null}
              />
            )}
          />
        </EmptyWidgets.Provider>
      </div>
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
