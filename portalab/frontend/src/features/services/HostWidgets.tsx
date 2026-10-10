import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { CompactLine } from "../dashboard/widgets/compact";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import "./hosts.css";

/**
 * Servers (#49 Glances, #50 Unraid): « Server » (processor, memory, hottest sensor, network, uptime, what
 * needs attention), « Storage » (the whole, each disk and cache, the array and its parity check) and
 * « Containers » (how many run, which have an update, the server's unread notifications). On one row, each
 * says its essentials in a line.
 */
interface UsageData {
  used: number;
  total: number;
}

interface HostData {
  name: string;
  hostname?: string | null;
  os?: string | null;
  cpu_name?: string | null;
  cpu_cores?: number | null;
  uptime_seconds?: number | null;
  cpu?: number | null;
  memory?: UsageData | null;
  storage?: UsageData | null;
  temperature?: { label: string; value: number } | null;
  network?: { rx: number; tx: number } | null;
  containers?: { running: number; total: number } | null;
  updates?: number;
  warnings: string[];
}

/** « 19.5 TB » — bytes in the largest fitting unit. */
export function useBytes() {
  const { locale } = useLocaleContext();
  return (bytes: number | null | undefined, digits = 1): string => {
    if (bytes === null || bytes === undefined) return "—";
    const units = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte", "petabyte"];
    let value = bytes;
    let index = 0;
    while (value >= 1000 && index < units.length - 1) {
      value /= 1000;
      index += 1;
    }
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit: units[index],
      unitDisplay: "short",
      maximumFractionDigits: value >= 100 ? 0 : digits,
    }).format(value);
  };
}

/** A known word for a server's value, or the value itself. */
function known(t: ReturnType<typeof useT>, key: string, fallback: string): string {
  const text = t(key);
  return text === key.split(":").slice(1).join(":") ? fallback.toLowerCase().replace(/_/g, " ") : text;
}

const percent = (usage: UsageData | null | undefined): number | null =>
  usage && usage.total ? Math.round((100 * usage.used) / usage.total) : null;

/** A level for a share: calm under 75 %, warm under 90 %, hot above. */
const level = (value: number | null | undefined, warm = 75, hot = 90): string =>
  value === null || value === undefined ? "none" : value >= hot ? "hot" : value >= warm ? "warm" : "ok";

function Gauge({
  label,
  value,
  text,
  tone,
}: {
  label: string;
  value: number | null;
  text: string;
  tone: string;
}) {
  return (
    <div
      className="host-gauge"
      data-level={tone}
      style={{ "--value": Math.max(0, Math.min(100, value ?? 0)) } as CSSProperties}
      role="img"
      aria-label={`${label}: ${text}`}
    >
      <span className="host-gauge__ring" aria-hidden="true">
        <strong>{text}</strong>
      </span>
      <span className="host-gauge__label">{label}</span>
    </div>
  );
}

function useUptime() {
  const t = useT();
  return (seconds: number | null | undefined) => {
    if (!seconds) return null;
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    return days
      ? t("dashboard:host.uptimeDays", { days, hours })
      : t("dashboard:host.uptimeHours", { hours });
  };
}

function Warnings({ codes }: { codes: string[] }) {
  const t = useT();
  if (!codes.length)
    return (
      <span className="host-ok">
        <Icon name="check" size={14} />
        {t("dashboard:host.allGood")}
      </span>
    );
  return (
    <ul className="host-warnings">
      {codes.map((code) => (
        <li key={code}>
          <Icon name="warning" size={14} />
          {t(`dashboard:host.warning.${code}`)}
        </li>
      ))}
    </ul>
  );
}

function HostWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const bytes = useBytes();
  const uptime = useUptime();
  const data = payload.data as unknown as HostData | undefined;
  if (!data) return null;
  const memory = percent(data.memory);
  const cpu = data.cpu !== null && data.cpu !== undefined ? Math.round(data.cpu) : null;
  const temp = data.temperature?.value ?? null;
  const title = data.hostname ?? data.name;
  if (compact)
    return (
      <CompactLine
        to="/services"
        icon="cpu"
        title={title}
        detail={[
          cpu !== null ? `CPU ${cpu} %` : null,
          memory !== null ? `RAM ${memory} %` : null,
          temp !== null ? `${Math.round(temp)} °C` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
        end={
          data.warnings.length ? (
            <span className="host-chip" data-level="hot">
              <Icon name="warning" size={14} />
              {data.warnings.length}
            </span>
          ) : (
            <span className="host-chip" data-level="ok">
              <Icon name="check" size={14} />
            </span>
          )
        }
      />
    );
  return (
    <div className="host-widget">
      <div className="host-widget__head">
        <span className="host-widget__name">
          <strong>{title}</strong>
          <small>{[data.os, uptime(data.uptime_seconds)].filter(Boolean).join(" · ")}</small>
        </span>
        <Warnings codes={data.warnings} />
      </div>
      <div className="host-gauges">
        <Gauge
          label={t("dashboard:host.cpu")}
          value={cpu}
          text={cpu !== null ? `${cpu} %` : "—"}
          tone={level(cpu, 70, 90)}
        />
        <Gauge
          label={t("dashboard:host.memory")}
          value={memory}
          text={memory !== null ? `${memory} %` : "—"}
          tone={level(memory, 80, 92)}
        />
        {temp !== null ? (
          <Gauge
            label={t("dashboard:host.temperature")}
            value={temp}
            text={`${Math.round(temp)} °C`}
            tone={level(temp, 70, 85)}
          />
        ) : null}
        {data.storage ? (
          <Gauge
            label={t("dashboard:host.storage")}
            value={percent(data.storage)}
            text={`${percent(data.storage)} %`}
            tone={level(percent(data.storage), 85, 95)}
          />
        ) : null}
      </div>
      <p className="host-widget__facts">
        {data.cpu_name ? (
          <span>
            <Icon name="cpu" size={14} />
            {data.cpu_name}
            {data.cpu_cores ? ` · ${t("dashboard:host.threads", { count: data.cpu_cores })}` : ""}
          </span>
        ) : null}
        {data.memory ? (
          <span>
            <Icon name="layers" size={14} />
            {bytes(data.memory.used)} / {bytes(data.memory.total)}
          </span>
        ) : null}
        {data.network ? (
          <span>
            <Icon name="arrow-down" size={14} />
            {bytes(data.network.rx)}/s
            <Icon name="arrow-up" size={14} />
            {bytes(data.network.tx)}/s
          </span>
        ) : null}
        {data.containers ? (
          <span>
            <Icon name="package" size={14} />
            {t("dashboard:host.containers", {
              running: data.containers.running,
              total: data.containers.total,
            })}
            {data.updates ? ` · ${t("dashboard:host.updates", { count: data.updates })}` : ""}
          </span>
        ) : null}
      </p>
    </div>
  );
}

interface StorageData {
  name: string;
  storage?: UsageData | null;
  array_state?: string | null;
  parity?: { status: string; progress?: number | null; errors?: number | null } | null;
  volumes: Array<{
    name: string;
    kind: string;
    used?: number | null;
    total?: number | null;
    ok: boolean;
    temperature?: number | null;
    spinning?: boolean | null;
  }>;
  warnings: string[];
}

function Bar({ used, total, tone }: { used: number; total: number; tone: string }) {
  return (
    <span className="host-bar" data-level={tone} aria-hidden="true">
      <span style={{ inlineSize: `${Math.min(100, (100 * used) / Math.max(total, 1))}%` }} />
    </span>
  );
}

function StorageWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const bytes = useBytes();
  const data = payload.data as unknown as StorageData | undefined;
  if (!data) return null;
  const whole = data.storage;
  const share = percent(whole);
  if (compact)
    return (
      <CompactLine
        to="/services"
        icon="database"
        title={whole ? t("dashboard:storage.used", { percent: share ?? 0 }) : data.name}
        detail={whole ? `${bytes(whole.used)} / ${bytes(whole.total)}` : undefined}
        end={whole ? <Bar used={whole.used} total={whole.total} tone={level(share, 85, 95)} /> : null}
      />
    );
  const running = data.parity && data.parity.status.toLowerCase() === "running";
  return (
    <div className="storage-widget">
      {whole ? (
        <div className="storage-widget__whole">
          <span className="storage-widget__figure">
            <strong>{share} %</strong>
            <small>
              {t("dashboard:storage.free", { free: bytes(whole.total - whole.used) })} · {bytes(whole.used)} /{" "}
              {bytes(whole.total)}
            </small>
          </span>
          <Bar used={whole.used} total={whole.total} tone={level(share, 85, 95)} />
        </div>
      ) : null}
      <p className="storage-widget__state">
        {data.array_state ? (
          <span className="host-chip" data-level={data.array_state === "STARTED" ? "ok" : "hot"}>
            <Icon name={data.array_state === "STARTED" ? "check" : "warning"} size={14} />
            {known(t, `dashboard:storage.array.${data.array_state}`, data.array_state)}
          </span>
        ) : null}
        {running ? (
          <span className="host-chip" data-level="warm">
            <Icon name="sync" size={14} />
            {t("dashboard:storage.parity", { progress: Math.round(data.parity?.progress ?? 0) })}
          </span>
        ) : null}
        {data.warnings
          .filter((w) => w !== "array_stopped")
          .map((w) => (
            <span key={w} className="host-chip" data-level="hot">
              <Icon name="warning" size={14} />
              {t(`dashboard:host.warning.${w}`)}
            </span>
          ))}
      </p>
      <ul className="storage-widget__volumes">
        {data.volumes.map((volume) => {
          const share =
            volume.used !== null && volume.used !== undefined && volume.total
              ? Math.round((100 * volume.used) / volume.total)
              : null;
          return (
            <li
              key={`${volume.kind}-${volume.name}`}
              data-kind={volume.kind}
              data-ok={volume.ok || undefined}
            >
              <span className="storage-widget__name">
                <Icon
                  name={volume.kind === "parity" ? "shield" : volume.kind === "cache" ? "zap" : "database"}
                  size={14}
                />
                {volume.name}
              </span>
              {share !== null && volume.total ? (
                <Bar used={volume.used ?? 0} total={volume.total} tone={level(share, 85, 95)} />
              ) : (
                <span className="storage-widget__parity">{t(`dashboard:storage.kind.${volume.kind}`)}</span>
              )}
              <span className="storage-widget__value">
                {share !== null ? `${share} %` : volume.total ? bytes(volume.total) : ""}
              </span>
              <span className="storage-widget__temp" data-level={level(volume.temperature, 45, 55)}>
                {volume.temperature ? (
                  `${Math.round(volume.temperature)} °C`
                ) : volume.spinning === false ? (
                  <Icon name="moon" size={13} label={t("dashboard:storage.asleep")} />
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface ContainersData {
  name: string;
  running: number;
  total: number;
  updates: number;
  updates_known: boolean;
  items: Array<{ name: string; state: string; image?: string | null; update?: boolean | null }>;
  notices: Array<{ title: string; importance: string; detail: string }>;
}

function ContainersWidget({ payload, compact, config }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = payload.data as unknown as ContainersData | undefined;
  if (!data) return null;
  const summary = t("dashboard:host.containers", { running: data.running, total: data.total });
  if (compact)
    return (
      <CompactLine
        to="/services"
        icon="package"
        title={summary}
        detail={data.updates_known ? t("dashboard:host.updates", { count: data.updates }) : undefined}
        end={
          data.updates ? (
            <span className="host-chip" data-level="warm">
              <Icon name="arrow-up" size={14} />
              {format.number(data.updates)}
            </span>
          ) : null
        }
      />
    );
  // without update information (Glances), « up to date » would be a guess: say what runs instead
  const asked = String(config.show ?? "updates");
  const show = asked === "updates" && !data.updates_known ? "stopped" : asked;
  return (
    <div className="containers-widget">
      <p className="containers-widget__counts">
        <span className="host-chip" data-level={data.running === data.total ? "ok" : "warm"}>
          <Icon name="package" size={14} />
          {summary}
        </span>
        {data.updates_known ? (
          <span className="host-chip" data-level={data.updates ? "warm" : "ok"}>
            <Icon name="arrow-up" size={14} />
            {t("dashboard:host.updates", { count: data.updates })}
          </span>
        ) : null}
      </p>
      {data.notices.length ? (
        <ul className="containers-widget__notices">
          {data.notices.map((notice, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: notifications have no stable id here
            <li key={index} data-importance={notice.importance}>
              <Icon
                name={
                  notice.importance === "alert"
                    ? "alert"
                    : notice.importance === "warning"
                      ? "warning"
                      : "info"
                }
                size={14}
              />
              <span>
                <strong>{notice.title}</strong>
                {notice.detail ? <small>{notice.detail}</small> : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {data.items.length ? (
        <ul className="containers-widget__list">
          {data.items.map((item) => (
            <li key={item.name} data-state={item.state}>
              <span className="containers-widget__dot" aria-hidden="true" />
              <span className="containers-widget__name">
                <strong>{item.name}</strong>
                {item.image ? <small>{item.image}</small> : null}
              </span>
              {item.update ? (
                <span className="host-chip" data-level="warm">
                  {t("dashboard:host.updateAvailable")}
                </span>
              ) : (
                <span className="containers-widget__state">
                  {known(t, `dashboard:host.state.${item.state}`, item.state)}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="settings-muted">{t(`dashboard:host.none.${show}`)}</p>
      )}
    </div>
  );
}

registerWidgetComponent("health.host", HostWidget);
registerWidgetComponent("health.storage", StorageWidget);
registerWidgetComponent("health.containers", ContainersWidget);

/** The raw report of ``/infrastructure/hosts/{id}`` as the three widgets' data (the service page's panel). */
interface RawReport {
  hostname?: string | null;
  os?: string | null;
  cpu_name?: string | null;
  cpu_cores?: number | null;
  uptime_seconds?: number | null;
  cpu_percent?: number | null;
  memory?: UsageData | null;
  storage?: UsageData | null;
  array_state?: string | null;
  parity?: StorageData["parity"];
  volumes?: StorageData["volumes"];
  sensors?: Array<{ label: string; value: number; unit: string }>;
  interfaces?: Array<{ rx_bps?: number | null; tx_bps?: number | null }>;
  containers?: Array<{
    name: string;
    state: string;
    image?: string | null;
    update_available?: boolean | null;
  }>;
  notices?: ContainersData["notices"];
  warnings?: string[];
}

function payloadsOf(name: string, report: RawReport) {
  const temps = (report.sensors ?? []).filter((s) => s.unit === "°C");
  const hottest = temps.length ? temps.reduce((a, b) => (b.value > a.value ? b : a)) : null;
  const containers = report.containers ?? [];
  const interfaces = report.interfaces ?? [];
  const host: HostData = {
    name,
    hostname: report.hostname ?? null,
    os: report.os ?? null,
    cpu_name: report.cpu_name ?? null,
    cpu_cores: report.cpu_cores ?? null,
    uptime_seconds: report.uptime_seconds ?? null,
    cpu: report.cpu_percent ?? null,
    memory: report.memory ?? null,
    storage: report.storage ?? null,
    temperature: hottest ? { label: hottest.label, value: hottest.value } : null,
    network: interfaces.length
      ? {
          rx: interfaces.reduce((sum, i) => sum + (i.rx_bps ?? 0), 0),
          tx: interfaces.reduce((sum, i) => sum + (i.tx_bps ?? 0), 0),
        }
      : null,
    containers: containers.length
      ? { running: containers.filter((c) => c.state === "running").length, total: containers.length }
      : null,
    updates: containers.filter((c) => c.update_available).length,
    warnings: report.warnings ?? [],
  };
  const storage: StorageData = {
    name,
    storage: report.storage ?? null,
    array_state: report.array_state ?? null,
    parity: report.parity ?? null,
    volumes: (report.volumes ?? []).filter((v) => v.kind !== "share" && v.kind !== "boot" && v.total),
    warnings: report.warnings ?? [],
  };
  const docker: ContainersData = {
    name,
    running: host.containers?.running ?? 0,
    total: containers.length,
    updates: host.updates ?? 0,
    updates_known: containers.some((c) => c.update_available !== null && c.update_available !== undefined),
    items: containers
      .filter((c) => c.update_available || c.state !== "running")
      .map((c) => ({
        name: c.name,
        state: c.state,
        image: c.image ?? null,
        update: c.update_available ?? null,
      })),
    notices: report.notices ?? [],
  };
  return { host, storage, docker };
}

/** A service's server, on its page (#49/#50) — for those who may see the infrastructure. */
export function HostPanel({ serviceId }: { serviceId: string }) {
  const t = useT();
  const host = useQuery({
    queryKey: ["infrastructure", "host", serviceId],
    retry: false,
    refetchInterval: 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/infrastructure/hosts/{service_id}", {
          params: { path: { service_id: serviceId } },
        })
      ).data as unknown as { name: string; state: string; report: RawReport | null },
  });
  const entry = host.data;
  if (!entry?.report) return null;
  const payloads = payloadsOf(entry.name, entry.report);
  const payload = (data: unknown) => ({ state: "available", data }) as unknown as WidgetProps["payload"];
  return (
    <section className="svc-detail__block host-panel" aria-label={t("dashboard:widget.host.title")}>
      <h4>{t("dashboard:widget.host.title")}</h4>
      <HostWidget payload={payload(payloads.host)} config={{}} />
      {payloads.storage.volumes.length || payloads.storage.storage ? (
        <>
          <h4>{t("dashboard:widget.storage.title")}</h4>
          <StorageWidget payload={payload(payloads.storage)} config={{}} />
        </>
      ) : null}
      {payloads.docker.total || payloads.docker.notices.length ? (
        <>
          <h4>{t("dashboard:widget.containers.title")}</h4>
          <ContainersWidget payload={payload(payloads.docker)} config={{ show: "updates" }} />
        </>
      ) : null}
    </section>
  );
}
