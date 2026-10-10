import {
  Component,
  type ErrorInfo,
  type ReactNode,
  type RefObject,
  Suspense,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Instance, useWidgetData } from "../api";
import { keyOf } from "../edit/EditSession";
import { TEMPLATES } from "../templates/Templates";
import { useOffscreen } from "../widgets/motion";
import { widgetComponent } from "../widgets/registry";
import { HeaderSlot, WidgetHeaderAction } from "./actions";
import { useEmptyReport } from "./emptiness";

/**
 * One widget in its own frame (spec 009 T012; R3, R12): own query, own error boundary and Suspense — a
 * crashing or failing widget shows its state here and never affects its siblings. States render only
 * through ``FunctionalState`` (theme-independent meaning; no widget-specific state styling).
 */
class FrameBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  override componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // reported by the observability client hook; never rethrown (other widgets stay up)
  }

  override render(): ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function Body({ instance, rows }: { instance: Instance; rows?: number | undefined }) {
  const t = useT();
  const widget = instance.widget;
  // #52: a widget set « live » refreshes every ``live_seconds`` (a chart that moves), else at its pace
  const config = (instance.config ?? {}) as { live?: unknown; live_seconds?: unknown };
  const live =
    config.live === true && typeof config.live_seconds === "number" ? Math.max(2, config.live_seconds) : null;
  const interval = live ?? (widget?.refresh_mode === "interval" ? (widget.refresh_interval_s ?? null) : null);
  const query = useWidgetData(instance.widget_key, instance.id ?? null, interval);
  const report = useEmptyReport();
  const hideWhenEmpty = Boolean((instance.config as Record<string, unknown> | undefined)?._hide_empty);
  const empty = hideWhenEmpty && query.data?.state === "no-data";
  useEffect(() => {
    report(keyOf(instance), empty);
  }, [report, instance, empty]);
  if (query.isPending) return <FunctionalState state="loading" />;
  if (query.isError) return <FunctionalState state="error" onRetry={() => query.refetch()} />;
  const payload = query.data;
  switch (payload.state) {
    case "unavailable":
      return <FunctionalState state="unavailable" onRetry={() => query.refetch()} />;
    case "error":
      return <FunctionalState state="error" onRetry={() => query.refetch()} />;
    case "unauthorized":
      return <FunctionalState state="unauthorized" />;
    case "no-data":
      // 027: a calm empty state with the widget's own icon, not a status pill
      return (
        <p className="widget-empty" data-state="no-data" role="status">
          <Icon name={widget?.icon ?? "sparkles"} size={28} />
          <span>{t("dashboard:widgetEmpty")}</span>
        </p>
      );
  }
  const Rendered =
    widgetComponent(widget?.component_id) ??
    (widget?.template ? TEMPLATES[widget.template as keyof typeof TEMPLATES] : undefined);
  return (
    <>
      {payload.state === "partial" ? (
        // 027: in words — a source did not answer, what shows may be incomplete (no time: it is now)
        <FunctionalState
          state="partial"
          label={t("dashboard:partialHint")}
          {...(payload.partial_reasons.length ? { detail: payload.partial_reasons.join(" · ") } : {})}
        />
      ) : payload.state === "stale" ? (
        <FunctionalState state="stale" asOf={payload.as_of ? new Date(payload.as_of) : undefined} />
      ) : null}
      {payload.config_invalid ? <p className="widget__meta">{t("dashboard:configInvalid")}</p> : null}
      <UnreadBadge data={payload.data} />
      {Rendered ? (
        <Rendered
          payload={payload}
          config={instance.config}
          icon={widget?.icon}
          compact={rows !== undefined && rows <= 1}
          rows={rows}
        />
      ) : null}
    </>
  );
}

/** 027 (#12): the lists that fill their block — their rows stretch to its bottom edge. */
const FILL = [
  ".widget-rows",
  ".widget-shortcuts",
  ".widget-links",
  ".widget-services__grid",
  ".dashboard-summary__list",
  ".daily-objectives__list",
  ".widget-activity:not(.widget-activity--compact)",
].join(", ");
const STRETCH = 2.4; // a row grows at most this much past its natural height

/**
 * 027: the content fits its block — list items that would spill over the bottom are left out (no inner
 * scrollbar) and counted; recomputed when the block is resized or the content changes. The count opens
 * the whole widget in a dialog, where nothing is left out.
 *
 * 027 (#12): and the rows that stay **fill** the block: measured at their natural height, they are then
 * laid out as exactly that many rows stretched to the block's bottom (at most ``STRETCH`` times their
 * height), their pictures and text growing with them — no hole under a list, no row cut in half.
 */
function useFit(ref: RefObject<HTMLElement | null>): number {
  const [hidden, setHidden] = useState(0);
  useEffect(() => {
    const body = ref.current;
    if (!body || typeof ResizeObserver === "undefined") return;
    let frame = 0;
    const measure = (limit: number): number => {
      let count = 0;
      for (const item of body.querySelectorAll<HTMLElement>("ul > li, ol > li")) {
        if (item.closest("svg, .recharts-wrapper, [data-nofit]")) continue;
        const box = item.getBoundingClientRect();
        // the first row of a list always stays (cropped if need be): a block never looks empty
        const first = item.parentElement?.firstElementChild?.getBoundingClientRect();
        const firstRow = !first || box.top <= first.top + 2;
        const over = box.height > 0 && box.bottom > limit && !firstRow;
        if (over !== item.hasAttribute("data-overflow")) item.toggleAttribute("data-overflow", over);
        if (over && !item.parentElement?.closest("li[data-overflow]")) count += 1;
      }
      return count;
    };
    const fit = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        // items are hidden with « visibility » (layout unchanged), so measuring never re-flows the content
        const lists = [...body.querySelectorAll<HTMLElement>(FILL)].filter(
          (list) => !list.closest("[data-nofit]") && !list.parentElement?.closest("[data-filled]"),
        );
        for (const list of lists) {
          list.removeAttribute("data-filled");
          list.style.removeProperty("--fit-rows");
          list.style.removeProperty("--fill-height");
        }
        // the « +N » button sits in the header: the rows may reach the block's bottom edge
        const limit = body.getBoundingClientRect().bottom;
        const count = measure(limit + 1);
        for (const list of lists) {
          const top = list.getBoundingClientRect().top;
          const shown = [...list.children].filter(
            (child): child is HTMLElement =>
              child instanceof HTMLElement && !child.hasAttribute("data-overflow"),
          );
          if (!shown.length) continue;
          const tops = new Set(shown.map((child) => Math.round(child.getBoundingClientRect().top)));
          const natural = Math.max(...shown.map((child) => child.getBoundingClientRect().bottom)) - top;
          const room = limit - top;
          if (natural <= 0 || room <= natural + 2) continue; // already full (or cropped): leave it be
          list.style.setProperty("--fit-rows", String(tops.size));
          // a lone row grows a little only: stretched, it would float in the middle of the block
          const stretch = tops.size === 1 ? 1.3 : STRETCH;
          list.style.setProperty("--fill-height", `${Math.floor(Math.min(room, natural * stretch))}px`);
          list.setAttribute("data-filled", "");
        }
        setHidden(count);
      });
    };
    const resized = new ResizeObserver(fit);
    resized.observe(body);
    const changed = new MutationObserver(fit);
    changed.observe(body, { childList: true, subtree: true });
    fit();
    return () => {
      resized.disconnect();
      changed.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [ref]);
  return hidden;
}

export function WidgetFrame({
  instance,
  rows,
  controls,
  handles,
}: {
  instance: Instance;
  /** 027: the rows it takes in this view (a phone may give it fewer than the desktop) */
  rows?: number | undefined;
  controls?: ReactNode;
  handles?: ReactNode;
}) {
  const t = useT();
  const headingId = useId();
  const body = useRef<HTMLDivElement>(null);
  const hidden = useFit(body);
  useOffscreen(body); // 027 (#29): animations pause out of sight
  const height = rows ?? instance.h;
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const title = instance.widget ? t(instance.widget.title_key) : instance.widget_key;
  // 027: the member may show the content alone — without its title, without its box, or both
  const frame = (instance.config ?? {}) as Record<string, unknown>;
  return (
    <section
      aria-labelledby={headingId}
      className="widget-frame"
      data-widget={instance.widget_key}
      data-tile={height <= 1 || undefined}
      data-no-title={frame._hide_title === true || undefined}
      data-no-box={frame._no_box === true || undefined}
      style={{ "--widget-w": instance.w, "--widget-h": height } as React.CSSProperties}
    >
      {handles}
      <header className="widget-frame__header">
        <h3 id={headingId} className="widget-frame__title">
          {instance.widget?.icon ? <Icon name={instance.widget.icon} size={18} /> : null}
          {title}
        </h3>
        {instance.mandatory && instance.locked ? (
          <span className="widget__badge" data-pinned title={t("dashboard:pinnedHint")}>
            <Icon name="lock" size={11} /> <span className="widget__badge-text">{t("dashboard:pinned")}</span>
          </span>
        ) : (
          <>
            {instance.mandatory ? <span className="widget__badge">{t("dashboard:mandatory")}</span> : null}
            {instance.locked ? <span className="widget__badge">{t("dashboard:locked")}</span> : null}
          </>
        )}
        <span className="widget-frame__tools">
          <span className="widget-frame__actions" ref={setSlot} />
          {hidden && instance.available ? (
            <Dialog
              size="lg"
              title={title}
              closeLabel={t("dashboard:close")}
              trigger={
                <button
                  type="button"
                  className="widget-frame__more"
                  aria-label={t("dashboard:seeAll", { count: hidden })}
                  title={t("dashboard:seeAll", { count: hidden })}
                >
                  +{hidden}
                  <Icon name="maximize" size={12} />
                </button>
              }
            >
              <div className="widget-frame__full" data-widget={instance.widget_key}>
                <FrameBoundary fallback={<FunctionalState state="error" />}>
                  <Suspense fallback={<FunctionalState state="loading" />}>
                    <Body instance={instance} />
                  </Suspense>
                </FrameBoundary>
              </div>
            </Dialog>
          ) : null}
        </span>
        {controls}
      </header>
      <div className="widget-frame__body" ref={body}>
        {instance.available ? (
          <HeaderSlot.Provider value={slot}>
            <FrameBoundary fallback={<FunctionalState state="error" />}>
              <Suspense fallback={<FunctionalState state="loading" />}>
                <Body instance={instance} rows={height} />
              </Suspense>
            </FrameBoundary>
          </HeaderSlot.Provider>
        ) : (
          <FunctionalState state="unavailable" label={t("dashboard:unavailableWidget")} />
        )}
      </div>
    </section>
  );
}

/** #48: a widget whose data counts what the member has not seen yet (``unread``) says it in its header. */
function UnreadBadge({ data }: { data: unknown }) {
  const t = useT();
  const count = typeof data === "object" && data !== null ? (data as { unread?: unknown }).unread : undefined;
  if (typeof count !== "number" || count <= 0) return null;
  return (
    <WidgetHeaderAction>
      <span className="widget-unread" title={t("dashboard:unread", { count })}>
        <span className="widget-unread__dot" aria-hidden="true" />
        {t("dashboard:unread", { count })}
      </span>
    </WidgetHeaderAction>
  );
}
