import type { ComponentType } from "react";
import type { WidgetPayload } from "../api";

/**
 * First-party widget components (spec 009): ``registerWidgetComponent(component_id, Component)``. Widgets
 * without a component render through a declarative template (``stat|list|chart|timeline|status``).
 */
export interface WidgetProps {
  payload: WidgetPayload;
  config: Record<string, unknown>;
  /** The widget's icon (027: shown on rows without an image). */
  icon?: string | null | undefined;
  /** 027: the widget sits on a single row — it shows its compact form (one line: the essentials). */
  compact?: boolean | undefined;
}

const components = new Map<string, ComponentType<WidgetProps>>();

export function registerWidgetComponent(id: string, component: ComponentType<WidgetProps>): void {
  components.set(id, component);
}

export function widgetComponent(id: string | null | undefined): ComponentType<WidgetProps> | undefined {
  return id ? components.get(id) : undefined;
}
