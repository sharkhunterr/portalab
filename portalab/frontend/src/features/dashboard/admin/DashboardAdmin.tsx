import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { api } from "../../../api/client";
import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import type { CatalogEntry, Instance } from "../api";
import { ConfigDialog } from "../edit/EditControls";
import type { Cell } from "../edit/EditSession";
import { WidgetFrame } from "../frame/WidgetFrame";
import { DashboardGrid } from "../grid/DashboardGrid";
import {
  autofit,
  derive,
  firstFree,
  type Item,
  move,
  normalize,
  resize,
  VIEW_COLUMNS,
  type View,
} from "../grid/engine";
import "../widgets/registered";
import "../dashboard.css";

/**
 * Issue 250 — the members' default dashboard, composed by its administrator (``dashboard.manage``) with the
 * members' own editor: the same grid and the same widgets drawn, dragged and resized (keyboard too), one
 * arrangement per screen if wanted, each widget's settings in the members' own window — and how far it is
 * locked, simply: free (the member changes it or removes it), always there (moved and set by the member,
 * never removed), locked (at this place, this size, with these settings). A first visit and « Default » get
 * it; always-there and locked widgets reach every member at once. The other widgets stay offered, or are
 * switched off for everyone. One save writes it all (``PUT /admin/dashboard/composition``).
 */
type Lock = "free" | "always" | "locked";
/** Issue 347: the welcome's play gauge — a free widget may be shown to some of its profiles only. */
const PROFILES = ["none", "progression", "collector", "full"] as const;
type Profile = (typeof PROFILES)[number];
type Place = { x: number; y: number; w: number; h: number };
interface Composed extends Place {
  widget_key: string;
  config: Record<string, unknown>;
  lock: Lock;
  move?: boolean;
  resize?: boolean;
  tablet?: Place;
  phone?: Place;
  roles?: string[];
  profiles?: Profile[] | undefined;
}
interface Composition {
  items: Composed[];
  disabled: string[];
}
interface WidgetInfo {
  key: string;
  title_key: string;
  icon?: string | null;
  sold?: boolean;
  size?: { default: { w: number; h: number } };
}

const KEY = ["admin", "dashboard", "composition"] as const;
const LOCKS: readonly Lock[] = ["free", "always", "locked"];
const LOCK_ICONS: Record<Lock, string> = { free: "user", always: "shield", locked: "lock" };
const VIEWS: Array<{ view: View; icon: string }> = [
  { view: "desktop", icon: "monitor" },
  { view: "tablet", icon: "tablet" },
  { view: "phone", icon: "smartphone" },
];

function errorText(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  const errors = error.extensions.errors as string[] | undefined;
  return [error.message, ...(errors ?? [])].join(" — ");
}

const placeOf = ({ x, y, w, h }: Place): Place => ({ x, y, w, h });

/** Where each widget sits on one screen: its own place there, or the computer's arrangement derived. */
export function cellsOf(items: readonly Composed[], view: View): Map<string, Cell> {
  const desktop = items.map((i) => ({ id: i.widget_key, ...placeOf(i) }));
  if (view === "desktop") return new Map(desktop.map(({ id, ...cell }) => [id, cell]));
  const columns = VIEW_COLUMNS[view];
  const derived = new Map(derive(desktop, columns).map(({ id, ...cell }) => [id, placeOf(cell)]));
  if (!items.some((i) => i[view])) return derived;
  const own = items.map((i) => ({
    id: i.widget_key,
    ...(i[view] ?? derived.get(i.widget_key) ?? { x: 0, y: 0, w: columns, h: i.h }),
  }));
  return new Map(normalize(own, columns).map(({ id, ...cell }) => [id, placeOf(cell)]));
}

/** The editor's draft: the composition, each screen's arrangement written back where it belongs. */
function useComposer(saved: Composition | undefined) {
  const [draft, setDraft] = useState<Composition | null>(null);
  const [view, setView] = useState<View>("desktop");
  useEffect(() => {
    if (saved) setDraft(saved);
  }, [saved]);
  const items = useMemo(() => draft?.items ?? [], [draft]);
  const columns = VIEW_COLUMNS[view];
  const cells = useMemo(() => cellsOf(items, view), [items, view]);
  const grid = useCallback(
    (from: Map<string, Cell>): Item[] => [...from].map(([id, cell]) => ({ id, ...cell, locked: false })),
    [],
  );
  const place = useCallback(
    (next: Item[]) =>
      setDraft((current) => {
        if (!current) return current;
        const at = new Map(next.map((i) => [i.id, placeOf(i)]));
        return {
          ...current,
          items: current.items.map((item) => {
            const cell = at.get(item.widget_key);
            if (!cell) return item;
            return view === "desktop" ? { ...item, ...cell } : { ...item, [view]: cell };
          }),
        };
      }),
    [view],
  );
  const update = (key: string, change: Partial<Composed>) =>
    setDraft((current) =>
      current
        ? { ...current, items: current.items.map((i) => (i.widget_key === key ? { ...i, ...change } : i)) }
        : current,
    );
  const add = (info: WidgetInfo) =>
    setDraft((current) => {
      if (!current) return current;
      const size = info.size?.default ?? { w: 6, h: 3 };
      const at = (v: View) => {
        const placed = grid(cellsOf(current.items, v));
        const w = v === "desktop" ? size.w : Math.min(size.w, VIEW_COLUMNS[v]);
        return { ...firstFree(placed, { w, h: size.h }, VIEW_COLUMNS[v]), w, h: size.h };
      };
      const own = (v: "tablet" | "phone") => (current.items.some((i) => i[v]) ? { [v]: at(v) } : {});
      const item: Composed = {
        widget_key: info.key,
        ...at("desktop"),
        config: {},
        lock: "free",
        ...own("tablet"),
        ...own("phone"),
      };
      return {
        items: [...current.items, item],
        disabled: current.disabled.filter((k) => k !== info.key),
      };
    });
  const remove = (key: string) =>
    setDraft((current) =>
      current ? { ...current, items: current.items.filter((i) => i.widget_key !== key) } : current,
    );
  const disable = (key: string, off: boolean) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            disabled: off ? [...current.disabled, key].sort() : current.disabled.filter((k) => k !== key),
          }
        : current,
    );
  /** A tablet or a phone back to the computer's arrangement (derived). */
  const followDesktop = () => {
    if (view === "desktop") return;
    setDraft((current) =>
      current
        ? {
            ...current,
            items: current.items.map(({ [view]: _own, ...rest }) => rest as Composed),
          }
        : current,
    );
  };
  const arranger = {
    move: (key: string, x: number, y: number) => place(move(grid(cells), key, { x, y }, columns)),
    resize: (key: string, w: number, h: number) => place(resize(grid(cells), key, { w, h }, columns)),
    preview: (key: string, to: Partial<Cell>): Item[] | null => {
      const items = grid(cells);
      const target = items.find((i) => i.id === key);
      if (!target) return items;
      return to.w !== undefined || to.h !== undefined
        ? resize(items, key, { w: to.w ?? target.w, h: to.h ?? target.h }, columns)
        : move(items, key, { x: to.x ?? target.x, y: to.y ?? target.y }, columns);
    },
  };
  return {
    draft,
    setDraft,
    items,
    view,
    setView,
    columns,
    cells,
    arranger,
    update,
    add,
    remove,
    disable,
    followDesktop,
    autofit: () => place(autofit(grid(cells), columns)),
    own: view !== "desktop" && items.some((i) => i[view]),
  };
}

/** A composed widget drawn as a member would see it (no row of its own: the default settings' data). */
function instanceOf(item: Composed, index: number, meta: CatalogEntry["widget"] | undefined): Instance {
  return {
    id: null,
    widget_key: item.widget_key,
    status: "active",
    position: index,
    ...placeOf(item),
    config: item.config,
    widget: meta ?? null,
    policy: "free",
    locked: false,
    mandatory: false,
    movable: true,
    resizable: true,
    removable: true,
    hideable: false,
    available: true,
    views: {},
  } as Instance;
}

function LockButton({ lock, onChange }: { lock: Lock; onChange: (next: Lock) => void }) {
  const t = useT();
  const next = LOCKS[(LOCKS.indexOf(lock) + 1) % LOCKS.length] as Lock;
  return (
    <button
      type="button"
      className="dash-lock"
      data-lock={lock}
      title={t(`dashboard:compose.lockHint.${lock}`)}
      aria-label={t("dashboard:compose.lockNow", { lock: t(`dashboard:compose.lock.${lock}`) })}
      onClick={() => onChange(next)}
    >
      <Icon name={LOCK_ICONS[lock]} size={14} />
      <span className="dash-lock__label">{t(`dashboard:compose.lock.${lock}`)}</span>
    </button>
  );
}

/** Issue 347: the play profiles a free widget is shown to — none ticked: every member. */
function ProfilesPicker({
  value,
  out,
  onChange,
}: {
  value: readonly Profile[];
  out: boolean;
  onChange: (next: Profile[]) => void;
}) {
  const t = useT();
  const id = useId();
  // a panel of the browser's top layer: never cut by the widget's frame, closed by Escape or a click outside
  return (
    <span className="dash-profiles" data-preview-out={out || undefined}>
      <button
        type="button"
        className="dash-profiles__pill"
        popoverTarget={id}
        title={t("dashboard:compose.profilesHint")}
        aria-label={`${t("dashboard:compose.profiles")}: ${
          value.length
            ? value.map((profile) => t(`onboarding:play.${profile}`)).join(", ")
            : t("dashboard:compose.profilesAll")
        }`}
      >
        <Icon name="users" size={14} />
        <span className="dash-profiles__label" aria-hidden="true">
          {value.length
            ? t("dashboard:compose.profilesSome", { count: value.length })
            : t("dashboard:compose.profilesEveryone")}
        </span>
      </button>
      <div id={id} popover="auto" className="dash-profiles__panel">
        <fieldset>
          <legend>{t("dashboard:compose.profiles")}</legend>
          <p>{t("dashboard:compose.profilesHint")}</p>
          {PROFILES.map((profile) => (
            <CheckboxField
              key={profile}
              label={t(`onboarding:play.${profile}`)}
              checked={value.includes(profile)}
              onChange={(event) =>
                onChange(PROFILES.filter((p) => (p === profile ? event.target.checked : value.includes(p))))
              }
            />
          ))}
        </fieldset>
      </div>
    </span>
  );
}

export default function DashboardAdmin() {
  const t = useT();
  const client = useQueryClient();
  const saved = useQuery({
    queryKey: KEY,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/dashboard/composition")).data as unknown as Composition,
  });
  const widgets = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: async () =>
      (
        (await api.GET("/api/v1/admin/dashboard/policies")).data as unknown as {
          widgets: WidgetInfo[];
        }
      ).widgets,
  });
  const catalog = useQuery({
    queryKey: ["dashboard", "catalog"],
    queryFn: async () => ((await api.GET("/api/v1/dashboard/catalog")).data ?? []) as CatalogEntry[],
  });
  const composer = useComposer(saved.data);
  const [done, setDone] = useState(false);
  // issue 347: the dashboard as one play profile gets it — the others' widgets shown faded
  const [seenAs, setSeenAs] = useState<Profile | "">("");
  const save = useMutation({
    mutationFn: async (composition: Composition) =>
      (
        await api.PUT("/api/v1/admin/dashboard/composition", {
          body: composition as never,
        })
      ).data as unknown as Composition,
    onSuccess: (next) => {
      client.setQueryData(KEY, next);
      setDone(true);
      void client.invalidateQueries({ queryKey: ["admin", "dashboard"] });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const dirty =
    Boolean(saved.data && composer.draft) && JSON.stringify(saved.data) !== JSON.stringify(composer.draft);
  useEffect(() => {
    if (dirty) setDone(false);
  }, [dirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  if (!composer.draft || !widgets.data)
    return <FunctionalState state={saved.isError || widgets.isError ? "unauthorized" : "loading"} />;
  const draft = composer.draft;
  const metas = new Map((catalog.data ?? []).map((entry) => [entry.key, entry.widget]));
  const infoOf = (key: string) => widgets.data.find((w) => w.key === key);
  const titleOf = (key: string) => {
    const info = infoOf(key);
    return info ? t(info.title_key) : key;
  };
  const instances = composer.items.map((item, index) => instanceOf(item, index, metas.get(item.widget_key)));
  const spare = [...widgets.data]
    .filter((w) => !composer.items.some((i) => i.widget_key === w.key))
    .sort((a, b) => t(a.title_key).localeCompare(t(b.title_key)));
  const saveBar = (
    <div className="dashboard-admin__save" data-dirty={dirty || undefined}>
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {errorText(save.error, t("dashboard:admin.failed"))}
        </p>
      ) : done && !dirty ? (
        <p role="status">{t("dashboard:admin.saved")}</p>
      ) : dirty ? (
        <p role="status">{t("dashboard:admin.unsaved")}</p>
      ) : null}
      {dirty ? (
        <Button
          variant="ghost"
          disabled={save.isPending}
          onClick={() => saved.data && composer.setDraft(saved.data)}
        >
          <Icon name="undo" size={16} />
          {t("dashboard:compose.undo")}
        </Button>
      ) : null}
      <Button disabled={save.isPending || !dirty} onClick={() => save.mutate(draft)}>
        <Icon name="check" size={16} />
        {t("dashboard:admin.save")}
      </Button>
    </div>
  );
  return (
    <AdminPage
      icon="dashboard"
      title={t("dashboard:admin.title")}
      description={t("dashboard:compose.description")}
      primary={saveBar}
      wide
    >
      <section className="dashboard-toolbar" aria-label={t("dashboard:toolbar")}>
        <fieldset className="ds-subnav" aria-label={t("dashboard:screens")}>
          {VIEWS.map(({ view, icon }) => (
            <button
              key={view}
              type="button"
              aria-pressed={composer.view === view}
              onClick={() => composer.setView(view)}
            >
              <Icon name={icon} size={16} />
              {t(`dashboard:view.${view}`)}
            </button>
          ))}
        </fieldset>
        {spare.length ? (
          <SelectField
            label={t("dashboard:admin.add")}
            value=""
            onChange={(event) => {
              const info = infoOf(event.target.value);
              if (info) composer.add(info);
            }}
          >
            <option value="">—</option>
            {spare.map((w) => (
              <option key={w.key} value={w.key}>
                {t(w.title_key)}
                {w.sold ? ` · ${t("dashboard:admin.sold")}` : ""}
              </option>
            ))}
          </SelectField>
        ) : null}
        <SelectField
          label={t("dashboard:compose.seenAs")}
          value={seenAs}
          onChange={(event) => setSeenAs(event.target.value as Profile | "")}
        >
          <option value="">{t("dashboard:compose.profilesAll")}</option>
          {PROFILES.map((profile) => (
            <option key={profile} value={profile}>
              {t(`onboarding:play.${profile}`)}
            </option>
          ))}
        </SelectField>
        <Button variant="secondary" onClick={composer.autofit}>
          <Icon name="maximize" size={16} />
          {t("dashboard:autofit")}
        </Button>
        {composer.own ? (
          <Button variant="ghost" onClick={composer.followDesktop}>
            <Icon name="sync" size={16} />
            {t("dashboard:compose.followDesktop")}
          </Button>
        ) : null}
        <p className="dashboard-page__hint">
          {t("dashboard:compose.hint")}
          {composer.view !== "desktop" && !composer.own ? ` ${t("dashboard:compose.derived")}` : ""}
        </p>
      </section>
      <div
        className="dashboard-stage dashboard-compose"
        data-view={composer.view}
        data-preview={composer.view !== "desktop" || undefined}
      >
        <DashboardGrid
          label={t("dashboard:compose.grid")}
          instances={instances}
          cells={composer.cells}
          columns={composer.columns}
          arranger={composer.arranger}
          render={(instance, handles, cell) => {
            const item = composer.items.find((i) => i.widget_key === instance.widget_key) as Composed;
            return (
              <WidgetFrame
                instance={instance}
                rows={cell.h}
                handles={handles}
                controls={
                  <div
                    className="widget-frame__controls"
                    role="toolbar"
                    aria-label={titleOf(item.widget_key)}
                  >
                    <LockButton
                      lock={item.lock}
                      onChange={(lock) => composer.update(item.widget_key, { lock })}
                    />
                    {item.lock === "free" ? (
                      <ProfilesPicker
                        value={item.profiles ?? []}
                        out={Boolean(seenAs && item.profiles?.length && !item.profiles.includes(seenAs))}
                        onChange={(profiles) =>
                          composer.update(item.widget_key, {
                            profiles: profiles.length ? profiles : undefined,
                          })
                        }
                      />
                    ) : null}
                    <ConfigDialog
                      key={JSON.stringify(item.config)}
                      instance={instance}
                      onSave={(config) => composer.update(item.widget_key, { config })}
                    />
                    <Button
                      variant="ghost"
                      className="dash-tool ds-button--quiet-danger"
                      size="icon"
                      aria-label={t("dashboard:admin.remove")}
                      title={t("dashboard:admin.remove")}
                      onClick={() => composer.remove(item.widget_key)}
                    >
                      <Icon name="trash" size={16} />
                    </Button>
                  </div>
                }
              />
            );
          }}
        />
      </div>
      <AdminSection
        span="full"
        icon="lock"
        title={t("dashboard:compose.locks")}
        description={t("dashboard:compose.locksHint")}
      >
        <ul className="dash-locks">
          {LOCKS.map((lock) => (
            <li key={lock}>
              <span className="dash-lock" data-lock={lock}>
                <Icon name={LOCK_ICONS[lock]} size={14} />
                {t(`dashboard:compose.lock.${lock}`)}
              </span>
              <span className="admin-muted">{t(`dashboard:compose.lockHint.${lock}`)}</span>
            </li>
          ))}
        </ul>
      </AdminSection>
      {spare.length ? (
        <AdminSection
          span="full"
          icon="apps"
          title={t("dashboard:compose.others")}
          description={t("dashboard:compose.othersHint")}
        >
          <ul className="dashboard-policies">
            {spare.map((widget) => (
              <li key={widget.key} className="dashboard-policy">
                <span className="dashboard-policy__name">
                  <Icon name={widget.icon ?? "dashboard"} size={18} />
                  <span>
                    <strong>{t(widget.title_key)}</strong>
                    <span className="admin-muted">
                      {widget.key}
                      {widget.sold ? ` · ${t("dashboard:admin.sold")}` : ""}
                    </span>
                  </span>
                </span>
                <CheckboxField
                  label={t("dashboard:compose.off")}
                  checked={draft.disabled.includes(widget.key)}
                  onChange={(event) => composer.disable(widget.key, event.target.checked)}
                />
                <Button variant="ghost" onClick={() => composer.add(widget)}>
                  <Icon name="plus" size={16} />
                  {t("dashboard:compose.place")}
                </Button>
              </li>
            ))}
          </ul>
        </AdminSection>
      ) : null}
    </AdminPage>
  );
}
