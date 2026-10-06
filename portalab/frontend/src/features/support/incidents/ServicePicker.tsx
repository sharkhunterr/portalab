import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";

interface ServiceItem {
  id: string;
  name: string;
  connector: string;
}

export function useServiceList() {
  return useQuery({
    queryKey: ["admin", "services", "picker"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/services")).data as unknown as { items: ServiceItem[] }).items.filter(
        (s) => s.id,
      ),
  });
}

/**
 * What an incident concerns (027): the whole server, or services ticked in the list of configured ones —
 * no ids to type. An empty selection means the whole server.
 */
export function ServicePicker({
  value,
  onChange,
  label,
}: {
  value: string[];
  onChange: (ids: string[]) => void;
  label: string;
}) {
  const t = useT();
  const services = useServiceList();
  const whole = value.length === 0;
  return (
    <fieldset className="service-picker">
      <legend>{label}</legend>
      <div className="ds-subnav">
        <button type="button" aria-pressed={whole} onClick={() => onChange([])}>
          <Icon name="server" size={14} />
          {t("support:console.wholeServer")}
        </button>
        <button
          type="button"
          aria-pressed={!whole}
          disabled={!services.data?.length}
          onClick={() => !value.length && services.data?.[0] && onChange([services.data[0].id])}
        >
          <Icon name="list" size={14} />
          {t("support:console.someServices")}
        </button>
      </div>
      {!whole ? (
        <div className="service-picker__list">
          {(services.data ?? []).map((service) => {
            const checked = value.includes(service.id);
            return (
              <label key={service.id} className="service-picker__item" data-checked={checked || undefined}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    onChange(checked ? value.filter((id) => id !== service.id) : [...value, service.id])
                  }
                />
                <span>{service.name}</span>
                <span className="service-picker__kind">{service.connector}</span>
              </label>
            );
          })}
        </div>
      ) : null}
    </fieldset>
  );
}
