import { type ReactNode, useId, useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import {
  imageUrl,
  MediaError,
  type MediaSection,
  useMediaDetail,
  useRequestActions,
  useSection,
} from "../api";
import "../media.css";
import { StatusBadge } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { Backdrop, Enrichment, useMetadata } from "./Enrichment";

/**
 * Media detail (spec 024 T017/T020): a header and independent section frames — each section loads, fails
 * and retries on its own, so one unavailable source only greys out its own frame. Availability, service
 * health and sync state are separate facts in the sources section (text, never color alone).
 */
const SECTIONS = [
  "info",
  "sources",
  "progress",
  "history",
  "requests",
  "people",
  "statistics",
  "events",
  "links",
  "blocks",
];
type Data = Record<string, unknown>;

const ICONS: Record<string, string> = {
  info: "book",
  sources: "server",
  progress: "target",
  history: "clock",
  requests: "inbox",
  people: "users",
  statistics: "chart",
  events: "activity",
  links: "link",
  blocks: "list",
};

function clock(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

function list(value: unknown): Data[] {
  return Array.isArray(value) ? (value as Data[]) : [];
}

function SectionBody({ name, section }: { name: string; section: MediaSection }) {
  const t = useT();
  const format = useFormat();
  const data = section.data as Data;
  switch (name) {
    case "info":
      return (
        <>
          {data.overview ? <p>{String(data.overview)}</p> : null}
          {list(data.children).length ? (
            <>
              <h4>{t("media:detail.children")}</h4>
              <ul className="media-chips">
                {list(data.children).map((child) => (
                  <li key={String(child.id)}>
                    <Link to={`/media/${String(child.id)}`}>{String(child.title)}</Link>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </>
      );
    case "sources":
      return (
        <ul className="media-list">
          {list(data.sources).map((source) => (
            <li key={String(source.service_id)} className="media-source">
              <strong>{String(source.service_name ?? source.connector ?? source.service_id)}</strong>
              <span className="media-source__badges">
                <StatusBadge tone={source.availability === "available" ? "ok" : "neutral"}>
                  {source.availability === "available"
                    ? t("media:detail.available")
                    : t("media:detail.unavailable")}
                </StatusBadge>
                {!source.present ? (
                  <StatusBadge tone="warn">{t("media:detail.source.gone")}</StatusBadge>
                ) : null}
                {source.sync_error ? (
                  <StatusBadge tone="bad">{t("media:detail.source.syncError")}</StatusBadge>
                ) : null}
                {source.service_state && source.service_state !== "operational" ? (
                  <StatusBadge tone="warn">
                    {t("media:detail.source.health", { state: String(source.service_state) })}
                  </StatusBadge>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      );
    case "progress":
      return data.state === "finished" ? (
        <p>{t("media:detail.finished")}</p>
      ) : (
        <p>
          {t("media:detail.progress", {
            percent: Math.round(Number(data.percent ?? 0) * 100),
            position: clock(Number(data.resume_position_s ?? 0)),
          })}
        </p>
      );
    case "history": {
      const mine = list(data.mine);
      const others = list(data.concerned_users);
      return (
        <>
          {mine.length === 0 ? <p>{t("media:detail.mine.none")}</p> : null}
          <ul className="media-list">
            {mine.map((entry) => (
              <li key={String(entry.occurred_at)}>
                {format.dateTime(String(entry.occurred_at))}
                {entry.completed ? ` · ${t("media:detail.finished")}` : ""}
              </li>
            ))}
          </ul>
          {others.length ? (
            <p>
              {t("media:detail.concerned")}: {others.map((u) => String(u.display_name)).join(", ")}
            </p>
          ) : null}
        </>
      );
    }
    case "requests":
      return (
        <>
          <p>{t("media:detail.openRequests", { count: Number(data.open_total ?? 0) })}</p>
          <ul className="media-list">
            {list(data.mine).map((r) => (
              <li key={String(r.id)}>{t(`media:requests.state.${String(r.state)}`)}</li>
            ))}
          </ul>
        </>
      );
    case "people":
      return <p>{(data.people as string[] | undefined)?.join(", ")}</p>;
    case "statistics":
      return <p>{t("media:detail.finishedBy", { count: Number(data.finished_by ?? 0) })}</p>;
    case "events":
      return (
        <ol className="media-list">
          {list(data.events).map((e) => (
            <li key={`${String(e.type)}-${String(e.at)}`}>
              {String(e.type)} · {format.dateTime(String(e.at))}
            </li>
          ))}
        </ol>
      );
    case "links":
      return (
        <ul className="media-chips">
          {list(data.links).map((l) => (
            <li key={String(l.url)}>
              <a href={String(l.url)} rel="noopener noreferrer external" target="_blank">
                {String(l.label)} <Icon name="link" size={14} />
              </a>
            </li>
          ))}
        </ul>
      );
    case "blocks":
      return (
        <>
          {list(data.blocks).map((b) => (
            <div key={String(b.key)}>
              <h4>{t(String(b.title_key))}</h4>
              {b.state === "available" ? (
                <dl>
                  {list((b.data as Data | undefined)?.rows).map((row) => {
                    const [label, value] = row as unknown as [string, string];
                    return (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    );
                  })}
                </dl>
              ) : (
                <FunctionalState state="unavailable" />
              )}
            </div>
          ))}
        </>
      );
    default:
      return null;
  }
}

/** Whether a section has something to show (027: empty sections are left out instead of « No data »). */
function hasContent(name: string, data: Data): boolean {
  switch (name) {
    case "info":
      return Boolean(data.overview) || list(data.children).length > 0;
    case "history":
      return list(data.mine).length > 0 || list(data.concerned_users).length > 0;
    case "requests":
      return Number(data.open_total ?? 0) > 0 || list(data.mine).length > 0;
    case "people":
      return Array.isArray(data.people) && data.people.length > 0;
    case "statistics":
      return Number(data.finished_by ?? 0) > 0;
    case "events":
      return list(data.events).length > 0;
    case "links":
      return list(data.links).length > 0;
    case "blocks":
      return list(data.blocks).some((b) => b.state === "available");
    case "sources":
      return list(data.sources).length > 0;
    default:
      return true;
  }
}

function SectionFrame({ objectId, name }: { objectId: string; name: string }) {
  const t = useT();
  const headingId = useId();
  const section = useSection(objectId, name);
  const state = section.data?.state;
  // nothing to tell: the section is left out (while loading too, to avoid a page of spinners)
  if (section.isPending) return null;
  if (state === "no-data" || state === "insufficient_data") return null;
  if (section.data && state !== "unavailable" && !hasContent(name, section.data.data as Data)) return null;
  let body: ReactNode = null;
  if (section.isPending) body = <FunctionalState state="loading" />;
  else if (section.isError) body = <FunctionalState state="unavailable" onRetry={() => section.refetch()} />;
  else if (section.data) {
    const state = section.data.state;
    if (state === "unavailable")
      body = <FunctionalState state="unavailable" onRetry={() => section.refetch()} />;
    else if (state === "insufficient_data")
      body = <FunctionalState state="no-data" label={t("media:detail.insufficient")} />;
    else if (state === "no-data") body = <FunctionalState state="no-data" />;
    else
      body = (
        <>
          {state === "partial" || state === "stale" ? (
            <FunctionalState state={state} asOf={new Date(section.data.as_of)} />
          ) : null}
          <SectionBody name={name} section={section.data} />
        </>
      );
  }
  return (
    <section aria-labelledby={headingId} className="media-section" data-section={name}>
      <h3 id={headingId}>
        <Icon name={ICONS[name] ?? "list"} size={18} />
        {t(`media:detail.section.${name}`)}
      </h3>
      {body}
    </section>
  );
}

function RequestButton({ objectId }: { objectId: string }) {
  const t = useT();
  const { submit } = useRequestActions();
  const [key] = useState(() => `detail-${objectId}-${Date.now()}`);
  const error = submit.error instanceof MediaError ? submit.error : null;
  return (
    <div>
      <Button
        onClick={() => submit.mutate({ object_id: objectId, idempotency_key: key })}
        disabled={submit.isPending}
      >
        {t("media:detail.request")}
      </Button>
      <p aria-live="polite">
        {submit.isSuccess ? t("media:requests.submitted") : null}
        {error?.code === "media.request_quota_exceeded" ? t("media:requests.quotaExceeded") : null}
        {error && error.code !== "media.request_quota_exceeded" ? t("media:requests.failed") : null}
      </p>
    </div>
  );
}

export function DetailPage() {
  const t = useT();
  const { objectId = "" } = useParams();
  const headingId = useId();
  const detail = useMediaDetail(objectId);
  // with enriched details (TMDB), the cast and the technical timeline would only repeat or distract
  const enriched = Boolean(useMetadata(objectId).data);
  if (detail.isPending) return <FunctionalState state="loading" />;
  if (detail.isError || !detail.data)
    return <FunctionalState state="unavailable" onRetry={() => detail.refetch()} />;
  const media = detail.data;
  const poster = imageUrl(media.image_id);
  return (
    <article aria-labelledby={headingId} className="media-detail">
      <Backdrop objectId={media.id} />
      <PageHeader
        titleId={headingId}
        level={2}
        artwork={poster}
        title={
          <>
            {media.title} {media.year ? <span className="media-muted">({media.year})</span> : null}
          </>
        }
        context={
          <>
            {t(`media:kind.${media.kind}`)} ·{" "}
            {media.available ? t("media:detail.available") : t("media:detail.unavailable")}
            {media.genres.length ? ` · ${media.genres.join(", ")}` : ""}
          </>
        }
        primary={media.available ? null : <RequestButton objectId={media.id} />}
      />
      <Enrichment objectId={media.id} />
      <div className="media-sections">
        {SECTIONS.filter((name) => !(enriched && (name === "people" || name === "events"))).map((name) => (
          <SectionFrame key={name} objectId={media.id} name={name} />
        ))}
      </div>
    </article>
  );
}

export default DetailPage;
