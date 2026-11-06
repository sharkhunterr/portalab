import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import {
  AdminEmpty,
  AdminSection,
  AdminStats,
  AdminTable,
  AdminTabs,
  FormActions,
  FormGrid,
  StatusBadge,
  type Tone,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, TextField } from "../../design-system/components/Field";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import {
  type AskConfig,
  type Asked,
  type AskStatus,
  OPEN,
  useAskQueue,
  useDecide,
  useSaveAskConfig,
} from "./api";
import "../admin/admin.css";
import "./requests.css";

/**
 * Issue 363: the members' requests for titles no service asks for, for the team (issue 375: two tabs of the
 * media's « Requests » page) — the queue (the open and
 * most wanted first, who wants each), moved on in a click (accepted, in progress, refused with the reason the
 * members read, there: the library's title, found by a search), and the module's settings: the kinds of
 * titles open to requests, a quota per kind, what a request costs. Closed by itself once the library has the
 * title.
 */
const TONE: Record<AskStatus, Tone> = {
  new: "warn",
  accepted: "info",
  in_progress: "info",
  available: "ok",
  refused: "bad",
  cancelled: "neutral",
};
const NEXT: Record<AskStatus, AskStatus[]> = {
  new: ["accepted", "in_progress"],
  accepted: ["in_progress"],
  in_progress: ["accepted"],
  refused: ["new"],
  available: [],
  cancelled: [],
};

function Found({ item, onPick }: { item: Asked; onPick: (id: string) => void }) {
  const t = useT();
  const [q, setQ] = useState(item.title);
  const found = useQuery({
    queryKey: ["requests", "pick", item.kind, q],
    enabled: q.trim().length >= 2,
    queryFn: async () =>
      (
        (await api.GET("/api/v1/media", { params: { query: { kind: item.kind, q, limit: 6 } as never } }))
          .data as unknown as { items: { id: string; title: string; year?: number | null }[] }
      ).items,
  });
  return (
    <div className="asks-pick">
      <TextField label={t("media:ask.admin.pick")} value={q} onChange={(e) => setQ(e.target.value)} />
      <ul className="asks-wanted" aria-label={t("media:ask.admin.pick")}>
        {(found.data ?? []).map((title) => (
          <li key={title.id}>
            <Button variant="secondary" onClick={() => onPick(title.id)}>
              {[title.title, title.year].filter(Boolean).join(" · ")}
            </Button>
          </li>
        ))}
      </ul>
      {found.data && !found.data.length ? (
        <p className="asks-muted">{t("media:ask.admin.pickNone")}</p>
      ) : null}
    </div>
  );
}

function Actions({ item }: { item: Asked }) {
  const t = useT();
  const decide = useDecide();
  const [mode, setMode] = useState<"refuse" | "there" | null>(null);
  const [reason, setReason] = useState("");
  const error = decide.error instanceof ApiError ? decide.error.message : null;
  if (mode === "refuse") {
    return (
      <form
        className="asks-pick"
        onSubmit={(event) => {
          event.preventDefault();
          decide.mutate({ id: item.id, status: "refused", reason }, { onSuccess: () => setMode(null) });
        }}
      >
        <TextField
          label={t("media:ask.admin.reason")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          required
        />
        <FormActions>
          <Button variant="ghost" onClick={() => setMode(null)}>
            {t("media:ask.admin.back")}
          </Button>
          <Button type="submit" variant="danger" disabled={!reason.trim() || decide.isPending}>
            {t("media:ask.admin.refuse")}
          </Button>
        </FormActions>
        {error ? <p role="alert">{error}</p> : null}
      </form>
    );
  }
  if (mode === "there") {
    return (
      <div className="asks-pick">
        <Found
          item={item}
          onPick={(object_id) =>
            decide.mutate({ id: item.id, status: "available", object_id }, { onSuccess: () => setMode(null) })
          }
        />
        <Button variant="ghost" onClick={() => setMode(null)}>
          {t("media:ask.admin.back")}
        </Button>
        {error ? <p role="alert">{error}</p> : null}
      </div>
    );
  }
  return (
    <div className="asks-row__side">
      {NEXT[item.status].map((status) => (
        <Button
          key={status}
          variant="secondary"
          disabled={decide.isPending}
          onClick={() => decide.mutate({ id: item.id, status: status as Exclude<AskStatus, "cancelled"> })}
        >
          {t(`media:ask.admin.to.${status}`)}
        </Button>
      ))}
      {OPEN.includes(item.status) ? (
        <>
          <Button variant="secondary" onClick={() => setMode("there")}>
            {t("media:ask.admin.to.available")}
          </Button>
          <Button variant="danger" onClick={() => setMode("refuse")}>
            {t("media:ask.admin.refuse")}
          </Button>
        </>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}

function Queue({
  status,
  setStatus,
}: {
  status: AskStatus | "all";
  setStatus: (s: AskStatus | "all") => void;
}) {
  const t = useT();
  const format = useFormat();
  const queue = useAskQueue(status);
  if (queue.isPending) return <FunctionalState state="loading" />;
  if (!queue.data) return <FunctionalState state="unavailable" onRetry={() => queue.refetch()} />;
  const figures = queue.data.figures;
  const open = OPEN.reduce((sum, s) => sum + (figures[s] ?? 0), 0);
  return (
    <>
      <AdminStats
        label={t("media:ask.admin.figures")}
        stats={[
          { key: "open", label: t("media:ask.admin.open"), value: format.number(open), tone: "warn" },
          {
            key: "available",
            label: t("media:ask.status.available"),
            value: format.number(figures.available ?? 0),
            tone: "ok",
          },
          {
            key: "refused",
            label: t("media:ask.status.refused"),
            value: format.number(figures.refused ?? 0),
            tone: "bad",
          },
        ]}
      />
      <AdminSection title={t("media:ask.admin.queue")} flush>
        <AdminTabs
          label={t("media:ask.admin.filter")}
          current={status}
          onChange={(key) => setStatus(key as AskStatus | "all")}
          tabs={[
            { key: "all", label: t("media:ask.admin.all") },
            ...queue.data.statuses.map((s) => ({
              key: s,
              label: t(`media:ask.status.${s}`),
              count: figures[s] ?? 0,
            })),
          ]}
        />
        <AdminTable
          label={t("media:ask.admin.queue")}
          rows={queue.data.requests}
          rowKey={(row) => row.id}
          empty={
            <AdminEmpty
              icon="inbox"
              title={t("media:ask.admin.empty")}
              action={<Link to="/requests">{t("media:ask.admin.emptyAction")}</Link>}
            />
          }
          columns={[
            {
              key: "title",
              header: t("media:ask.admin.title"),
              primary: true,
              render: (row) => (
                <div className="asks-row__main">
                  <strong className="asks-row__title">
                    {row.route ? <Link to={row.route}>{row.title}</Link> : row.title}
                  </strong>
                  <span className="asks-muted">
                    {[
                      t(`media:kind.${row.kind}`),
                      row.creators.join(", "),
                      row.year,
                      ...Object.values(row.details),
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                  {row.note ? <span className="asks-muted">« {row.note} »</span> : null}
                  {row.reason ? <span className="asks-row__reason">{row.reason}</span> : null}
                </div>
              ),
            },
            {
              key: "wanted",
              header: t("media:ask.admin.wantedBy"),
              render: (row) => (
                <ul className="asks-wanted">
                  {(row.wanted_by ?? []).map((who) => (
                    <li key={`${who.name}-${who.since}`}>
                      {who.name}
                      {who.asked ? ` · ${t("media:ask.admin.askedFirst")}` : ""}
                    </li>
                  ))}
                </ul>
              ),
            },
            {
              key: "status",
              header: t("media:ask.admin.status"),
              render: (row) => (
                <span className="asks-row__main">
                  <StatusBadge tone={TONE[row.status]}>{t(`media:ask.status.${row.status}`)}</StatusBadge>
                  <span className="asks-muted">{format.date(new Date(row.updated_at), "medium")}</span>
                </span>
              ),
            },
          ]}
          actions={(row) => <Actions item={row} />}
        />
      </AdminSection>
    </>
  );
}

function Settings() {
  const t = useT();
  const queue = useAskQueue("all");
  const save = useSaveAskConfig();
  const [config, setConfig] = useState<AskConfig | null>(null);
  useEffect(() => {
    if (queue.data && config === null) setConfig(queue.data.config);
  }, [queue.data, config]);
  if (!queue.data || !config) return <FunctionalState state="loading" />;
  const toggle = (kind: string, on: boolean) =>
    setConfig({
      ...config,
      kinds: on ? [...config.kinds, kind] : config.kinds.filter((k) => k !== kind),
    });
  const quota = (kind: string, field: "limit" | "days", value: number) =>
    setConfig({
      ...config,
      quotas: {
        ...config.quotas,
        [kind]: { limit: 0, days: 30, ...config.quotas[kind], [field]: value },
      },
    });
  return (
    <AdminSection title={t("media:ask.admin.settings")} description={t("media:ask.admin.settingsHint")}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(config);
        }}
      >
        <FormGrid>
          {queue.data.known_kinds.map((kind) => (
            <CheckboxField
              key={kind}
              label={t(`media:kind.${kind}`)}
              checked={config.kinds.includes(kind)}
              onChange={(e) => toggle(kind, e.target.checked)}
            />
          ))}
        </FormGrid>
        {config.kinds.map((kind) => (
          <FormGrid key={kind}>
            <TextField
              label={t("media:ask.admin.quotaLimit", { kind: t(`media:kind.${kind}`) })}
              hint={t("media:ask.admin.quotaHint")}
              type="number"
              min={0}
              max={1000}
              value={config.quotas[kind]?.limit ?? 0}
              onChange={(e) => quota(kind, "limit", Number(e.target.value))}
            />
            <TextField
              label={t("media:ask.admin.quotaDays")}
              type="number"
              min={1}
              max={365}
              value={config.quotas[kind]?.days ?? 30}
              onChange={(e) => quota(kind, "days", Number(e.target.value))}
            />
          </FormGrid>
        ))}
        <FormGrid>
          <TextField
            label={t("media:ask.admin.price", { currency: t("gamification:value.coins") })}
            hint={t("media:ask.admin.priceHint")}
            type="number"
            min={0}
            value={config.price}
            onChange={(e) => setConfig({ ...config, price: Number(e.target.value) })}
          />
        </FormGrid>
        <FormActions>
          <Button type="submit" disabled={save.isPending}>
            {t("media:ask.admin.save")}
          </Button>
        </FormActions>
        {save.isSuccess ? <p role="status">{t("media:ask.admin.saved")}</p> : null}
        {save.isError ? <p role="alert">{t("media:ask.error.failed")}</p> : null}
      </form>
    </AdminSection>
  );
}

/** Issue 375: the title requests in the media's « Requests » page — their queue, or their settings. */
export function TitleRequests({ settings = false }: { settings?: boolean }) {
  const [status, setStatus] = useState<AskStatus | "all">("all");
  return settings ? <Settings /> : <Queue status={status} setStatus={setStatus} />;
}

/** Whether the title requests answer (the module switched on, the member allowed to handle them). */
export function useTitleRequestsOn(): boolean {
  return Boolean(useAskQueue("all").data);
}
