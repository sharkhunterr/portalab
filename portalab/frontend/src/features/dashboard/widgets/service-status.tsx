import { CONNECTOR_ICON } from "../../services/connectorIcons";
import { HealthBadge, type OverviewItem, ServiceCard, UptimeBars } from "../../services/ServicesHealth";
import { CompactLine } from "./compact";
import { registerWidgetComponent, type WidgetProps } from "./registry";

/**
 * « Service status » (027): one service as on the services page — its state, its last 48 hours as bars,
 * its availability, its address and details; on a single row, its name, the bars and the state. Several
 * can be placed, one per service.
 */
function ServiceStatus({ payload, compact }: WidgetProps) {
  const item = ((payload.data ?? {}) as { item?: OverviewItem & { route?: string } }).item;
  if (!item) return null;
  if (compact)
    return (
      <div className="widget-service-status widget-service-status--compact">
        <CompactLine
          to={item.route}
          icon={CONNECTOR_ICON[item.connector] ?? "server"}
          title={item.name}
          detail={<UptimeBars serviceId={item.id} />}
          end={<HealthBadge state={item.state} />}
        />
      </div>
    );
  return (
    <ul className="widget-service-status">
      <ServiceCard item={item} />
    </ul>
  );
}

registerWidgetComponent("health.service_status", ServiceStatus);
