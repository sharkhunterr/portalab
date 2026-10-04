import { Component, type ErrorInfo, type ReactNode, Suspense, useId } from "react";
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
      return <FunctionalState state="no-data" />;
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
      {Rendered ? <Rendered payload={payload} config={instance.config} /> : null}
    </>
  );
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
      {instance.available ? (
        <FrameBoundary fallback={<FunctionalState state="error" />}>
          <Suspense fallback={<FunctionalState state="loading" />}>
            <Body instance={instance} />
          </Suspense>
        </FrameBoundary>
      ) : (
        <FunctionalState state="unavailable" label={t("dashboard:unavailableWidget")} />
      )}
      {controls}
    </section>
  );
}
