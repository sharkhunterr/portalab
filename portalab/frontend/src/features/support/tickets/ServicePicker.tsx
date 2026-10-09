import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { connectorIcon } from "../../services/connectorIcons";

interface PublicService {
  id: string;
  name: string;
  connector: string | null;
  state: string;
}

const KNOWN = ["operational", "degraded", "unavailable", "maintenance", "unknown"];

/**
 * 027 (#27): which service the ticket is about — the services members see on the status page, as buttons
 * (one at most, or none), each with its icon and its state when it is not running fine. Shares the status
 * page's query.
 */
export function ServicePicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const t = useT();
  const name = useId();
  const services = useQuery({
    queryKey: ["services", "health"],
    queryFn: async () =>
      ((await api.GET("/api/v1/services/health")).data as unknown as { items: PublicService[] }).items,
  });
  const items = services.data ?? [];
  if (!items.length) return null;
  const option = (id: string, label: string, icon: string, state: string | null) => (
    <label key={id || "none"} className="service-picker__option" data-selected={value === id || undefined}>
      <input type="radio" name={name} value={id} checked={value === id} onChange={() => onChange(id)} />
      <Icon name={icon} size={16} />
      <span className="service-picker__name">{label}</span>
      {state && state !== "operational" ? (
        <span className="service-picker__state" data-state={state}>
          {t(`dashboard:health.${KNOWN.includes(state) ? state : "unknown"}`)}
        </span>
      ) : null}
    </label>
  );
  return (
    <fieldset className="service-picker">
      <legend>{t("support:new.service")}</legend>
      <div className="service-picker__options">
        {option("", t("support:new.noService"), "minus", null)}
        {items.map((s) => option(s.id, s.name, connectorIcon(s.connector), s.state))}
      </div>
    </fieldset>
  );
}
