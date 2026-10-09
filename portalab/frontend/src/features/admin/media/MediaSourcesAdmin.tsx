import { Link } from "react-router";
import {
  AdminEmpty,
  AdminPage,
  AdminSection,
  AdminStats,
  AdminTable,
  LiveProgress,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Progress } from "../../../design-system/components/Content";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Source, useResync, useRunNow, useSources } from "../../media/insights/api";
import "../admin.css";

/**
 * History and metadata (027, Services hub — administration only): where the play history of each service
 * stands (catching up, up to date, failing) with its live progress, the TMDB enrichment of the catalog,
 * the plays not tied to a member yet; update now, enrich now, or start a history over. Members only ever
 * read the statistics; nothing here is reachable from their pages.
 */
function SourceState({ source }: { source: Source }) {
  const t = useT();
  const format = useFormat();
  const p = source.progress;
  if (p.running) {
    return (
      <LiveProgress
        label={t(
          source.mode === "backfill" ? "media:insights.sources.catchingUp" : "media:insights.sources.reading",
        )}
        done={p.done}
        total={p.total}
        detail={p.total ? `${format.number(p.done ?? 0)} / ${format.number(p.total)}` : null}
      />
    );
  }
  if (source.last_error) {
    return (
      <span className="services-admin__name">
        <StatusBadge tone="bad">{t("media:insights.sources.error")}</StatusBadge>
        <span className="admin-muted">{source.last_error}</span>
      </span>
    );
  }
  if (source.behind_since) {
    // #24: another source of the same server goes on recording plays (Tautulli no longer told by Plex)
    return (
      <span className="services-admin__name">
        <StatusBadge tone="warn">{t("media:insights.sources.behind")}</StatusBadge>
        <span className="admin-muted">
          {t("media:insights.sources.behindSince", { date: format.dateTime(source.behind_since) })}
        </span>
      </span>
    );
  }
  if (source.mode === "backfill") {
    return (
      <span className="insights-source-state">
        <StatusBadge tone="info">{t("media:insights.sources.backfill")}</StatusBadge>
        {p.total ? (
          <span className="admin-muted">
            {t("media:insights.sources.paused", { percent: format.percent((p.done ?? 0) / p.total) })}
          </span>
        ) : null}
      </span>
    );
  }
  return <StatusBadge tone="ok">{t("media:insights.sources.live")}</StatusBadge>;
}

export default function MediaSourcesAdmin() {
  const t = useT();
  const format = useFormat();
  const sources = useSources(true);
  const resync = useResync();
  const run = useRunNow();
  const data = sources.data;
  const meta = data?.metadata;
  const attempted = meta ? Math.min(meta.found + meta.missing + meta.error, meta.eligible) : 0;
  const plays = (data?.sources ?? []).reduce((sum, s) => sum + s.items, 0);
  return (
    <AdminPage
      icon="chart"
      title={t("media:sources.title")}
      description={t("media:sources.subtitle")}
      primary={
        <Button disabled={run.isPending} onClick={() => run.mutate("history")}>
          <Icon name="sync" size={16} />
          {t("media:insights.sources.runNow")}
        </Button>
      }
      secondary={
        <Link className="ds-button ds-button--ghost" to="/media/insights?scope=all">
          <Icon name="chart" size={16} />
          {t("media:sources.openStatistics")}
        </Link>
      }
    >
      {run.isSuccess ? (
        <p role="status" className="services-admin__ok">
          {t("media:insights.sources.queued")}
        </p>
      ) : null}
      {data ? (
        <>
          <AdminStats
            label={t("media:sources.title")}
            stats={[
              {
                key: "plays",
                label: t("media:sources.plays"),
                value: format.number(plays),
                icon: "activity",
                tone: "info",
              },
              {
                key: "unattributed",
                label: t("media:sources.unattributed"),
                value: format.number(data.unattributed),
                icon: "link",
                tone: data.unattributed ? "warn" : "ok",
                to: "/admin/members?tab=accounts",
                hint: data.unattributed ? t("media:insights.mapAccounts") : undefined,
              },
              {
                key: "metadata",
                label: t("media:sources.enriched"),
                value: meta?.provider
                  ? `${format.number(meta.found)} / ${format.number(meta.eligible)}`
                  : "—",
                icon: "sparkles",
                tone: meta?.provider ? "info" : "neutral",
              },
            ]}
          />
          <AdminSection
            title={t("media:insights.sources.title")}
            description={t("media:insights.sources.hint")}
            icon="server"
            flush
          >
            <AdminTable<Source>
              label={t("media:insights.sources.title")}
              rows={data.sources}
              rowKey={(s) => s.service_id}
              empty={
                <AdminEmpty
                  icon="server"
                  title={t("media:insights.sources.none")}
                  action={<Link to="/admin/services">{t("media:sources.addService")}</Link>}
                />
              }
              columns={[
                {
                  key: "name",
                  header: t("media:insights.sources.service"),
                  primary: true,
                  render: (s) => <strong>{s.name}</strong>,
                },
                {
                  key: "state",
                  header: t("media:insights.sources.state"),
                  render: (s) => <SourceState source={s} />,
                },
                {
                  key: "items",
                  header: t("media:insights.sources.items"),
                  render: (s) => format.number(s.items),
                },
                {
                  key: "last",
                  header: t("media:insights.sources.last"),
                  render: (s) =>
                    s.last_run_at ? format.relative((Date.parse(s.last_run_at) - Date.now()) / 1000) : "—",
                },
              ]}
              actions={(s) =>
                s.source === "history" ? (
                  <Button
                    variant="ghost"
                    disabled={resync.isPending}
                    onClick={() => resync.mutate(s.service_id)}
                    aria-label={`${t("media:insights.sources.resync")} ${s.name}`}
                  >
                    <Icon name="sync" size={16} />
                    {t("media:insights.sources.resync")}
                  </Button>
                ) : null
              }
            />
          </AdminSection>
          <AdminSection
            title={t("media:sources.metadataTitle")}
            description={t("media:sources.metadataHint")}
            icon="sparkles"
            actions={
              meta?.provider ? (
                <Button variant="secondary" disabled={run.isPending} onClick={() => run.mutate("metadata")}>
                  <Icon name="sparkles" size={16} />
                  {t("media:insights.sources.enrichNow")}
                </Button>
              ) : null
            }
          >
            {!meta?.provider ? (
              <AdminEmpty
                icon="sparkles"
                title={t("media:insights.sources.noMetadata")}
                action={<Link to="/admin/services">{t("media:sources.addService")}</Link>}
              />
            ) : meta.progress.running ? (
              <LiveProgress
                label={t("media:insights.sources.enriching")}
                done={attempted}
                total={meta.eligible}
                detail={`${format.number(attempted)} / ${format.number(meta.eligible)}`}
              />
            ) : (
              <Progress
                label={t("media:insights.sources.enriched", {
                  done: format.number(attempted),
                  total: format.number(meta.eligible),
                })}
                value={attempted}
                max={Math.max(meta.eligible, 1)}
              />
            )}
            {meta?.provider ? (
              <p className="admin-muted">
                {t("media:insights.sources.metadata", {
                  found: format.number(meta.found),
                  missing: format.number(meta.missing),
                })}
              </p>
            ) : null}
          </AdminSection>
        </>
      ) : null}
    </AdminPage>
  );
}
