import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import type { WidgetPayload } from "../api";
import { TEMPLATES } from "../templates/Templates";
import { widgetComponent } from "../widgets/registry";
import { previewPayload } from "./mocks";
import "../widgets/tiles";
import "../widgets/layout";
import "../widgets/builtin";
import "../widgets/media";
import "../widgets/calendar";
import "../widgets/discover";
import "../../gamification/widget";
import "../../community/widget";
import "../widgets/skins"; // 027 (#30): last — the looks wrap the widgets above, a look's product shows it

/**
 * 027: a widget's miniature — the real widget with the member's own data (``preview``: before it is bought,
 * the permission still applies), scaled down and inert; with nothing to show yet, sample data (mocks.ts).
 * Loaded only when it comes into view; the icon stands in while loading.
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
  const shown =
    data.isSuccess || data.isError ? previewPayload(data.data, widget.component_id, widget.template) : null;
  const live = Boolean(Rendered && shown);
  return (
    <span
      ref={box}
      className={`widget-preview ${className ?? ""}`}
      data-live={live || undefined}
      aria-hidden="true"
    >
      {live && Rendered && shown ? (
        <span className="widget-preview__scaled" inert data-sample={shown.sample || undefined}>
          <Rendered payload={shown.payload} config={widget.config_defaults ?? {}} icon={widget.icon} />
        </span>
      ) : (
        <Icon name={widget.icon ?? "dashboard"} size={26} />
      )}
    </span>
  );
}
