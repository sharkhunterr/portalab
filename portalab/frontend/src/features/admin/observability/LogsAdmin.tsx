import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api/client";
import { AdminPage, AdminSection, StatusBadge, type Tone } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import "../admin.css";
import "./logs.css";

/**
 * The log journal (issue 158, Monitoring): the server's and the worker's lines — already redacted by the
 * server — newest first, followed live (paused at will), filtered by level, source, process, period, text
 * and correlation id; a line opens on its structured fields, copies, and the selection exports as text or
 * JSON. Readings and exports are audited by the server.
 */
export interface LogLine {
  seq: number;
  at: string;
  process: string;
  level: string;
  logger: string;
  source: string;
  message: string;
  correlation_id: string | null;
  fields: Record<string, unknown>;
}

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;
const LEVEL_LOOK: Record<string, { tone: Tone; icon: string }> = {
  DEBUG: { tone: "neutral", icon: "bug" },
  INFO: { tone: "info", icon: "info" },
  WARNING: { tone: "warn", icon: "warning" },
  ERROR: { tone: "bad", icon: "alert" },
  CRITICAL: { tone: "bad", icon: "flame" },
};
const PERIODS = { "15m": 15, "1h": 60, "24h": 1_440, "7d": 10_080, all: 0 } as const;
type Period = keyof typeof PERIODS;
const LIVE_EVERY_MS = 3_000;
const KEPT = 1_000; // lines kept on the page while following live

interface Filters {
  levels: string[];
  source: string;
  process: string;
  period: Period;
  text: string;
  correlation: string;
  requests: boolean;
}

interface LogQuery {
  level?: Array<(typeof LEVELS)[number]>;
  source?: string[];
  exclude?: string[];
  process?: string;
  q?: string;
  correlation?: string;
  since?: string;
}

function queryOf(filters: Filters): LogQuery {
  const query: LogQuery = {};
  const minutes = PERIODS[filters.period];
  if (filters.levels.length) query.level = filters.levels as Array<(typeof LEVELS)[number]>;
  if (filters.source) query.source = [filters.source];
  else if (!filters.requests) query.exclude = ["http", "http.out"]; // one line per request: hidden unless asked
  if (filters.process) query.process = filters.process;
  if (filters.text.trim()) query.q = filters.text.trim();
  if (filters.correlation) query.correlation = filters.correlation;
  if (minutes) query.since = new Date(Date.now() - minutes * 60_000).toISOString();
  return query;
}

function exportHref(filters: Filters, format: "text" | "json") {
  const search = new URLSearchParams({ format });
  for (const [key, value] of Object.entries(queryOf(filters))) {
    if (Array.isArray(value)) for (const item of value) search.append(key, item);
    else if (value) search.set(key, value);
  }
  return `/api/v1/admin/observability/logs/export?${search.toString()}`;
}

function useDebounced<T>(value: T, ms = 350): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

function LevelBadge({ level }: { level: string }) {
  const look = LEVEL_LOOK[level] ?? { tone: "neutral" as Tone, icon: "info" };
  return (
    <span className="logs-line__level" data-level={level.toLowerCase()}>
      <StatusBadge tone={look.tone}>
        <Icon name={look.icon} size={12} /> {level}
      </StatusBadge>
    </span>
  );
}

function LineDetail({ line, onCorrelation }: { line: LogLine; onCorrelation: (id: string) => void }) {
  const t = useT();
  const format = useFormat();
  const [copied, setCopied] = useState(false);
  const { exception, ...fields } = line.fields;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(line, null, 2));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="logs-line__detail">
      <dl className="logs-line__facts">
        <dt>{t("admin:logs.at")}</dt>
        <dd className="admin-mono">{format.dateTime(line.at)}</dd>
        <dt>{t("admin:logs.logger")}</dt>
        <dd className="admin-mono">{line.logger}</dd>
        <dt>{t("admin:logs.process")}</dt>
        <dd>{line.process}</dd>
        {line.correlation_id ? (
          <>
            <dt>{t("admin:logs.correlation")}</dt>
            <dd>
              <button
                type="button"
                className="logs-line__link admin-mono"
                onClick={() => onCorrelation(line.correlation_id ?? "")}
                title={t("admin:logs.byCorrelation")}
              >
                {line.correlation_id}
              </button>
            </dd>
          </>
        ) : null}
      </dl>
      <p className="logs-line__message admin-mono">{line.message}</p>
      {Object.keys(fields).length ? (
        <pre className="logs-line__fields admin-mono">{JSON.stringify(fields, null, 2)}</pre>
      ) : null}
      {typeof exception === "string" ? <pre className="logs-line__fields admin-mono">{exception}</pre> : null}
      <div className="logs-line__actions">
        <Button variant="secondary" onClick={() => void copy()}>
          <Icon name="link" size={14} /> {copied ? t("admin:logs.copied") : t("admin:logs.copy")}
        </Button>
      </div>
    </div>
  );
}

function Line({
  line,
  open,
  onToggle,
  onCorrelation,
}: {
  line: LogLine;
  open: boolean;
  onToggle: () => void;
  onCorrelation: (id: string) => void;
}) {
  const time = new Date(line.at).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return (
    <li className="logs-line" data-open={open || undefined} data-level={line.level.toLowerCase()}>
      <button type="button" className="logs-line__head" aria-expanded={open} onClick={onToggle}>
        <time className="logs-line__time admin-mono" dateTime={line.at}>
          {time}
        </time>
        <LevelBadge level={line.level} />
        <span className="logs-line__source">{line.source}</span>
        <span className="logs-line__process">{line.process}</span>
        <span className="logs-line__text admin-mono">{line.message}</span>
      </button>
      {open ? <LineDetail line={line} onCorrelation={onCorrelation} /> : null}
    </li>
  );
}

export function LogsAdmin() {
  const t = useT();
  const [levels, setLevels] = useState<string[]>([]);
  const [source, setSource] = useState("");
  const [process, setProcess] = useState("");
  const [period, setPeriod] = useState<Period>("24h");
  const [text, setText] = useState("");
  const [correlation, setCorrelation] = useState("");
  const [requests, setRequests] = useState(false);
  const [live, setLive] = useState(true);
  const [open, setOpen] = useState<number | null>(null);
  const [lines, setLines] = useState<LogLine[]>([]);
  const [older, setOlder] = useState<LogLine[]>([]);
  const [end, setEnd] = useState(false);
  const debounced = useDebounced(text);
  const filters: Filters = useMemo(
    () => ({ levels, source, process, period, text: debounced, correlation, requests }),
    [levels, source, process, period, debounced, correlation, requests],
  );

  const first = useQuery({
    queryKey: ["admin", "observability", "logs", filters],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/observability/logs", { params: { query: queryOf(filters) } })).data,
  });
  const [sources, setSources] = useState<string[]>([]);
  useEffect(() => {
    if (!first.data) return;
    setLines(first.data.items as LogLine[]);
    setOlder([]);
    setEnd(first.data.items.length < 200);
    if (first.data.sources) setSources(first.data.sources);
  }, [first.data]);

  // live: what came since the newest line, every few seconds, unless paused
  const newest = useRef(0);
  newest.current = lines[0]?.seq ?? newest.current;
  useEffect(() => {
    if (!live || !first.data) return;
    const timer = window.setInterval(async () => {
      try {
        const { data } = await api.GET("/api/v1/admin/observability/logs", {
          params: { query: { ...queryOf(filters), after: newest.current } },
        });
        if (data?.items.length) setLines((kept) => [...(data.items as LogLine[]), ...kept].slice(0, KEPT));
      } catch {
        // the next tick tries again
      }
    }, LIVE_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [live, filters, first.data]);

  const all = [...lines, ...older];
  const loadOlder = async () => {
    const last = all.at(-1);
    if (!last) return;
    const { data } = await api.GET("/api/v1/admin/observability/logs", {
      params: { query: { ...queryOf(filters), before: last.seq } },
    });
    const items = (data?.items ?? []) as LogLine[];
    setOlder((kept) => [...kept, ...items]);
    if (items.length < 200) setEnd(true);
  };
  const toggleLevel = (level: string) =>
    setLevels((chosen) => (chosen.includes(level) ? chosen.filter((l) => l !== level) : [...chosen, level]));

  return (
    <AdminPage
      icon="terminal"
      title={t("admin:logs.title")}
      description={t("admin:logs.subtitle")}
      wide
      primary={
        <Button variant={live ? "primary" : "secondary"} aria-pressed={live} onClick={() => setLive(!live)}>
          <Icon name={live ? "pause" : "play"} size={16} />{" "}
          {live ? t("admin:logs.pause") : t("admin:logs.resume")}
        </Button>
      }
      secondary={
        <span className="logs-export">
          <a className="ds-button ds-button--ghost" href={exportHref(filters, "text")} download>
            <Icon name="download" size={16} /> {t("admin:logs.exportText")}
          </a>
          <a className="ds-button ds-button--ghost" href={exportHref(filters, "json")} download>
            <Icon name="download" size={16} /> {t("admin:logs.exportJson")}
          </a>
        </span>
      }
    >
      <AdminSection title={t("admin:logs.filters")} icon="sliders" span="full">
        <div className="logs-filters">
          <fieldset className="logs-levels">
            <legend>{t("admin:logs.level")}</legend>
            {LEVELS.map((level) => (
              <button
                key={level}
                type="button"
                className="logs-levels__chip"
                data-level={level.toLowerCase()}
                aria-pressed={levels.includes(level)}
                onClick={() => toggleLevel(level)}
              >
                <Icon name={LEVEL_LOOK[level]?.icon ?? "info"} size={14} /> {level}
              </button>
            ))}
          </fieldset>
          <div className="logs-filters__wide">
            <CheckboxField
              label={t("admin:logs.requests")}
              hint={t("admin:logs.requestsHint")}
              checked={requests}
              onChange={(event) => setRequests(event.target.checked)}
            />
          </div>
          <SelectField
            label={t("admin:logs.source")}
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            <option value="">{t("admin:logs.allSources")}</option>
            {sources.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </SelectField>
          <SelectField
            label={t("admin:logs.process")}
            value={process}
            onChange={(event) => setProcess(event.target.value)}
          >
            <option value="">{t("admin:logs.allProcesses")}</option>
            <option value="serve">{t("admin:logs.serve")}</option>
            <option value="worker">{t("admin:logs.worker")}</option>
          </SelectField>
          <SelectField
            label={t("admin:logs.period")}
            value={period}
            onChange={(event) => setPeriod(event.target.value as Period)}
          >
            {(Object.keys(PERIODS) as Period[]).map((key) => (
              <option key={key} value={key}>
                {t(`admin:logs.periods.${key}`)}
              </option>
            ))}
          </SelectField>

          <TextField
            label={t("admin:logs.search")}
            type="search"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </div>
        {correlation ? (
          <p className="logs-correlation">
            {t("admin:logs.onlyCorrelation", { id: correlation })}{" "}
            <Button variant="ghost" onClick={() => setCorrelation("")}>
              <Icon name="close" size={14} /> {t("admin:logs.clear")}
            </Button>
          </p>
        ) : null}
      </AdminSection>
      <AdminSection
        title={t("admin:logs.lines")}
        icon="terminal"
        span="full"
        flush
        actions={
          <span className="logs-state" role="status">
            {live ? <span className="logs-state__dot" aria-hidden="true" /> : null}
            {live ? t("admin:logs.live") : t("admin:logs.paused")}
          </span>
        }
      >
        {first.isPending ? <p className="admin-muted admin-pad">{t("admin:logs.loading")}</p> : null}
        {first.isError ? <p className="admin-muted admin-pad">{t("admin:logs.failed")}</p> : null}
        {first.data && !all.length ? <p className="admin-muted admin-pad">{t("admin:logs.none")}</p> : null}
        <ol className="logs-list" aria-label={t("admin:logs.lines")}>
          {all.map((line) => (
            <Line
              key={line.seq}
              line={line}
              open={open === line.seq}
              onToggle={() => setOpen(open === line.seq ? null : line.seq)}
              onCorrelation={(id) => {
                setCorrelation(id);
                setOpen(null);
              }}
            />
          ))}
        </ol>
        {all.length && !end ? (
          <p className="admin-pad">
            <Button variant="secondary" onClick={() => void loadOlder()}>
              {t("admin:logs.older")}
            </Button>
          </p>
        ) : null}
      </AdminSection>
    </AdminPage>
  );
}
