import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import type { WidgetPayload } from "../api";
import { TEMPLATES } from "../templates/Templates";
import { widgetComponent } from "../widgets/registry";
import "../widgets/tiles";
import "../widgets/layout";
import "../widgets/builtin";
import "../widgets/media";
import "../widgets/calendar";

/**
 * 027: a widget's miniature — the real widget with the member's own data (``preview``: before it is bought,
 * the permission still applies), scaled down and inert. Loaded only when it comes into view; while loading,
 * or when it has nothing to show, its icon stands in.
 */
export interface PreviewWidget {
  key: string;
  icon?: string | null | undefined;
  template?: string | null | undefined;
  component_id?: string | null | undefined;
  config_defaults?: Record<string, unknown> | null | undefined;
}

export function WidgetPreview({ widget, className }: { widget: PreviewWidget; className?: string }) {
  const box = useRef<HTMLSpanElement>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const node = box.current;
    if (!node || seen) return;
    if (typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) setSeen(true);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [seen]);
  const data = useQuery({
    queryKey: ["widget", widget.key, "preview"],
    enabled: seen,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/widgets/{key}/data", {
          params: { path: { key: widget.key }, query: { preview: true } },
        })
      ).data as WidgetPayload,
  });
  const Rendered =
    widgetComponent(widget.component_id) ??
    (widget.template ? TEMPLATES[widget.template as keyof typeof TEMPLATES] : undefined);
  const live = Rendered && data.data && ["available", "partial", "stale"].includes(String(data.data.state));
  return (
    <span
      ref={box}
      className={`widget-preview ${className ?? ""}`}
      data-live={live || undefined}
      aria-hidden="true"
    >
      {live && Rendered && data.data ? (
        <span className="widget-preview__scaled" inert>
          <Rendered payload={data.data} config={widget.config_defaults ?? {}} icon={widget.icon} />
        </span>
      ) : (
        <Icon name={widget.icon ?? "dashboard"} size={26} />
      )}
    </span>
  );
}
