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
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Instance, useWidgetData } from "../api";
import { TEMPLATES } from "../templates/Templates";
import { widgetComponent } from "../widgets/registry";

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

function Body({ instance }: { instance: Instance }) {
  const t = useT();
  const widget = instance.widget;
  const interval = widget?.refresh_mode === "interval" ? (widget.refresh_interval_s ?? null) : null;
  const query = useWidgetData(instance.widget_key, instance.id ?? null, interval);
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
      {payload.state === "partial" || payload.state === "stale" ? (
        <FunctionalState
          state={payload.state}
          asOf={payload.as_of ? new Date(payload.as_of) : undefined}
          {...(payload.partial_reasons.length ? { detail: payload.partial_reasons.join(" · ") } : {})}
        />
      ) : null}
      {payload.config_invalid ? <p className="widget__meta">{t("dashboard:configInvalid")}</p> : null}
      {Rendered ? <Rendered payload={payload} config={instance.config} icon={widget?.icon} /> : null}
    </>
  );
}

/**
 * 027: the content fits its block — list items that would spill over the bottom are left out (no inner
 * scrollbar) and counted; recomputed when the block is resized or the content changes.
 */
function useFit(ref: RefObject<HTMLElement | null>): number {
  const [hidden, setHidden] = useState(0);
  useEffect(() => {
    const body = ref.current;
    if (!body || typeof ResizeObserver === "undefined") return;
    let frame = 0;
    const fit = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        // items are hidden with « visibility » (layout unchanged), so measuring never re-flows the content
        const limit = body.getBoundingClientRect().bottom + 1;
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
  controls,
  handles,
}: {
  instance: Instance;
  controls?: ReactNode;
  handles?: ReactNode;
}) {
  const t = useT();
  const headingId = useId();
  const body = useRef<HTMLDivElement>(null);
  const hidden = useFit(body);
  const title = instance.widget ? t(instance.widget.title_key) : instance.widget_key;
  return (
    <section
      aria-labelledby={headingId}
      className="widget-frame"
      data-widget={instance.widget_key}
      style={{ "--widget-w": instance.w, "--widget-h": instance.h } as React.CSSProperties}
    >
      {handles}
      <header className="widget-frame__header">
        <h3 id={headingId} className="widget-frame__title">
          {instance.widget?.icon ? <Icon name={instance.widget.icon} size={18} /> : null}
          {title}
        </h3>
        {instance.mandatory ? <span className="widget__badge">{t("dashboard:mandatory")}</span> : null}
        {instance.locked ? <span className="widget__badge">{t("dashboard:locked")}</span> : null}
      </header>
      <div className="widget-frame__body" ref={body}>
        {instance.available ? (
          <FrameBoundary fallback={<FunctionalState state="error" />}>
            <Suspense fallback={<FunctionalState state="loading" />}>
              <Body instance={instance} />
            </Suspense>
          </FrameBoundary>
        ) : (
          <FunctionalState state="unavailable" label={t("dashboard:unavailableWidget")} />
        )}
      </div>
      {hidden ? (
        <span className="widget-frame__more" title={t("dashboard:moreItems", { count: hidden })}>
          +{hidden}
        </span>
      ) : null}
      {controls}
    </section>
  );
}
