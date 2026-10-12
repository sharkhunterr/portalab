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
import { usePlayerInfo, useResetResume } from "../player/api";
import { artworkSlides, Backdrop, Enrichment, useMetadata } from "./Enrichment";
import { RequestJourney, useJourney } from "./Journey";
import { LeavingNotice } from "./Leaving";

/**
 * Media detail (spec 024 T017/T020): a header and independent section frames — each section loads, fails
 * and retries on its own, so one unavailable source only greys out its own frame. Availability, service
 * health and sync state are separate facts in the sources section (text, never color alone).
 */
// 027 (#22): « viewing » (my plays and how many watched it) replaces progress, history and statistics
const SECTIONS = ["info", "sources", "viewing", "requests", "people", "events", "links", "blocks"];
type Data = Record<string, unknown>;

const ICONS: Record<string, string> = {
  info: "book",
  sources: "server",
  progress: "target",
  history: "clock",
  requests: "inbox",
  people: "users",
  statistics: "chart",
  viewing: "clock",
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

/** A book's or an audiobook's facts (027, Grimmory): authors, series, publisher, pages, length… */
function BookFacts({ data }: { data: Data }) {
  const t = useT();
  const format = useFormat();
  const people = Array.isArray(data.people) ? (data.people as string[]) : [];
  const hours = data.duration_s ? Number(data.duration_s) / 3600 : 0;
  const rows = [
    people.length ? { key: "authors", value: people.join(", ") } : null,
    data.series
      ? {
          key: "series",
          value: data.series_position
            ? t("media:facts.seriesAt", {
                series: String(data.series),
                position: String(data.series_position),
              })
            : String(data.series),
        }
      : null,
    data.publisher ? { key: "publisher", value: String(data.publisher) } : null,
    data.released
      ? { key: "released", value: format.date(`${String(data.released)}T12:00:00Z`, "long") }
      : null,
    data.pages ? { key: "pages", value: t("media:facts.pageCount", { count: Number(data.pages) }) } : null,
    hours ? { key: "length", value: t("media:facts.hours", { hours: Math.round(hours * 10) / 10 }) } : null,
    data.language ? { key: "language", value: String(data.language).toUpperCase() } : null,
    data.isbn ? { key: "isbn", value: String(data.isbn) } : null,
  ].filter((row) => row !== null);
  const tags = Array.isArray(data.tags) ? (data.tags as string[]) : [];
  if (!rows.length && !tags.length) return null;
  return (
    <>
      <dl className="media-facts">
        {rows.map((row) => (
          <div key={row.key}>
            <dt>{t(`media:facts.${row.key}`)}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {tags.length ? (
        <ul className="media-enriched__chips" aria-label={t("media:facts.tags")}>
          {tags.map((tag) => (
            <li key={tag}>{tag}</li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

const BOOKS = ["book", "audiobook"];

/** 027: a game's facts (RomM): its platform, publisher and studios, release date, franchises and modes. */
function GameFacts({ data }: { data: Data }) {
  const t = useT();
  const format = useFormat();
  const companies = Array.isArray(data.people) ? (data.people as string[]) : [];
  const studios = companies.filter((c) => c !== data.publisher);
  const rows = [
    data.platform ? { key: "platform", value: String(data.platform) } : null,
    data.publisher ? { key: "publisher", value: String(data.publisher) } : null,
    studios.length ? { key: "studios", value: studios.join(", ") } : null,
    data.released
      ? { key: "releasedOn", value: format.date(`${String(data.released)}T12:00:00Z`, "long") }
      : data.year
        ? { key: "releasedOn", value: String(data.year) }
        : null,
  ].filter((row) => row !== null);
  const tags = Array.isArray(data.tags) ? (data.tags as string[]) : [];
  if (!rows.length && !tags.length) return null;
  return (
    <>
      <dl className="media-facts">
        {rows.map((row) => (
          <div key={row.key}>
            <dt>{t(`media:facts.${row.key}`)}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {tags.length ? (
        <ul className="media-enriched__chips" aria-label={t("media:facts.tags")}>
          {tags.map((tag) => (
            <li key={tag}>{tag}</li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

const SHOWN = 5;
const PLAYABLE = ["movie", "episode", "series", "season"];

/** 027 (#22): my plays of the title — newest first, how far, how long, on what — and, past the privacy
 * floor, how many plays and members it had (two figures, no names). */
function ViewingBody({ data }: { data: Data }) {
  const t = useT();
  const format = useFormat();
  const [all, setAll] = useState(false);
  const mine = list(data.mine);
  const community = data.community as { plays: number; viewers: number } | null | undefined;
  return (
    <>
      {community ? (
        <ul className="media-chips media-viewing-counts">
          <li>
            <Icon name="play" size={14} />
            {t("media:viewing.plays", { count: community.plays })}
          </li>
          <li>
            <Icon name="users" size={14} />
            {t("media:viewing.viewers", { count: community.viewers })}
          </li>
        </ul>
      ) : null}
      {mine.length ? (
        <ul className="media-viewing">
          {(all ? mine : mine.slice(0, SHOWN)).map((play) => {
            const share =
              play.progress === null || play.progress === undefined ? null : Number(play.progress);
            const details = [
              play.series ? String(play.title) : null,
              Number(play.watched_s) > 0 ? clock(Number(play.watched_s)) : null,
              play.device ? String(play.device) : null,
              play.quality ? String(play.quality).toUpperCase() : null,
            ].filter(Boolean);
            return (
              <li key={`${String(play.at)}-${String(play.title)}`}>
                <span className="media-viewing__when">{format.dateTime(String(play.at))}</span>
                <span className="media-viewing__bar" aria-hidden="true">
                  <span style={{ inlineSize: `${Math.round((share ?? 0) * 100)}%` }} />
                </span>
                <span className="media-viewing__share">
                  {share === null
                    ? "—"
                    : share >= 0.9
                      ? t("media:viewing.finished")
                      : `${Math.round(share * 100)} %`}
                </span>
                <span className="media-viewing__details">{details.join(" · ")}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="media-muted">{t("media:viewing.none")}</p>
      )}
      {mine.length > SHOWN ? (
        <button type="button" className="ds-button ds-button--quiet" onClick={() => setAll((v) => !v)}>
          {all
            ? t("media:viewing.less")
            : t("media:viewing.all", { count: Number(data.mine_total ?? mine.length) })}
        </button>
      ) : null}
    </>
  );
}

const SEEN_WORD: Record<string, string> = {
  book: "read",
  audiobook: "listened",
  game: "played",
  album: "listened",
};

/** 027 (#22): up top — is it here (or on its way), and did I see it already (or how far I am). */
function TitleBadges({ media }: { media: { id: string; kind: string; available: boolean } }) {
  const t = useT();
  const journey = useJourney(media.id).data as { request?: { state?: string } | null } | undefined;
  const player = usePlayerInfo(media.id, null, media.available && PLAYABLE.includes(media.kind)).data?.item;
  const viewing = (useSection(media.id, "viewing").data?.data ?? {}) as Data;
  const request = journey?.request?.state;
  const availability = media.available
    ? "available"
    : request === "processing"
      ? "downloading"
      : request === "pending" || request === "approved"
        ? "requested"
        : "unavailable";
  const resume =
    player && player.resume_s > 30 && (!player.duration_s || player.resume_s < player.duration_s * 0.95)
      ? player
      : null;
  const series = media.kind === "series" || media.kind === "season";
  const seen = !series && (Boolean(player?.watched) || viewing.status === "seen");
  const percent = resume?.duration_s
    ? resume.resume_s / resume.duration_s
    : viewing.status === "in_progress"
      ? Number(viewing.percent ?? 0)
      : null;
  return (
    <span className="media-badges">
      <span className="media-badge" data-tone={availability}>
        <Icon
          name={
            availability === "available"
              ? "check"
              : availability === "downloading"
                ? "package"
                : availability === "requested"
                  ? "hourglass"
                  : "blocked"
          }
          size={14}
        />
        {t(`media:badge.${availability}`)}
      </span>
      {resume && series && resume.label ? (
        <span className="media-badge" data-tone="progress">
          <Icon name="play" size={14} />
          {t("media:badge.inProgressEpisode", { label: resume.label })}
        </span>
      ) : percent !== null ? (
        <span className="media-badge" data-tone="progress">
          <Icon name="play" size={14} />
          {t("media:badge.inProgress", { percent: Math.round(percent * 100) })}
        </span>
      ) : null}
      {seen ? (
        <span className="media-badge" data-tone="seen">
          <Icon name="eye" size={14} />
          {t(`media:badge.seen.${SEEN_WORD[media.kind] ?? "watched"}`)}
        </span>
      ) : null}
    </span>
  );
}

function SectionBody({
  name,
  section,
  enriched,
}: {
  name: string;
  section: MediaSection;
  enriched: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const data = section.data as Data;
  switch (name) {
    case "info":
      return (
        <>
          {/* the enriched details already tell the story: no second summary (027) */}
          {data.overview && !enriched ? <p>{String(data.overview)}</p> : null}
          {BOOKS.includes(String(data.kind)) ? <BookFacts data={data} /> : null}
          {data.kind === "game" ? <GameFacts data={data} /> : null}
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
          {list(data.sources).map((source, index) => (
            // 027: a service may hold several copies of one title (a game per platform or region)
            // biome-ignore lint/suspicious/noArrayIndexKey: copies of one service share its id
            <li key={`${String(source.service_id)}-${index}`} className="media-source">
              <strong>{String(source.service_name ?? source.connector ?? source.service_id)}</strong>
              {source.variant ? (
                <span className="media-source__variant">{String(source.variant)}</span>
              ) : null}
              {source.link ? (
                <a
                  className="media-source__link"
                  href={String(source.link)}
                  target="_blank"
                  rel="noopener noreferrer external"
                >
                  {t("media:detail.source.open")} <Icon name="link" size={12} />
                </a>
              ) : null}
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
                  <span title={t("media:detail.source.syncErrorHint")}>
                    <StatusBadge tone="warn">
                      {source.last_sync_success_at
                        ? t("media:detail.source.syncStale", {
                            date: format.dateTime(String(source.last_sync_success_at)),
                          })
                        : t("media:detail.source.syncError")}
                    </StatusBadge>
                  </span>
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
    case "viewing":
      return <ViewingBody data={data} />;
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
function hasContent(name: string, data: Data, enriched = false): boolean {
  switch (name) {
    case "info":
      return (
        (Boolean(data.overview) && !enriched) ||
        list(data.children).length > 0 ||
        (BOOKS.includes(String(data.kind)) &&
          Boolean(data.people || data.series || data.publisher || data.pages)) ||
        (data.kind === "game" && Boolean(data.platform || data.publisher || data.people || data.released))
      );
    case "history":
      return list(data.mine).length > 0 || list(data.concerned_users).length > 0;
    case "requests":
      return Number(data.open_total ?? 0) > 0 || list(data.mine).length > 0;
    case "people":
      return Array.isArray(data.people) && data.people.length > 0;
    case "statistics":
      return Number(data.finished_by ?? 0) > 0;
    case "viewing":
      return list(data.mine).length > 0 || Boolean(data.community);
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

function SectionFrame({ objectId, name, enriched }: { objectId: string; name: string; enriched: boolean }) {
  const t = useT();
  const headingId = useId();
  const section = useSection(objectId, name);
  const state = section.data?.state;
  // nothing to tell: the section is left out (while loading too, to avoid a page of spinners)
  if (section.isPending) return null;
  if (state === "no-data" || state === "insufficient_data") return null;
  if (section.data && state !== "unavailable" && !hasContent(name, section.data.data as Data, enriched))
    return null;
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
          <SectionBody name={name} section={section.data} enriched={enriched} />
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

const WATCH = ["plex", "jellyfin", "emby"];
const READ = ["grimmory", "romm"];

/** 027: open the title where it is played or read — its own page in Plex, Jellyfin, Grimmory… */
function OpenIn({
  objectId,
  kind,
  secondary = false,
}: {
  objectId: string;
  kind: string;
  secondary?: boolean;
}) {
  const t = useT();
  const sources = useSection(objectId, "sources");
  const items = list((sources.data?.data as Data | undefined)?.sources).filter(
    (s) => s.item_link && s.availability === "available",
  );
  const rank = (s: Data) => {
    const connector = String(s.connector ?? "");
    const order = [...WATCH, ...READ].indexOf(connector);
    return order === -1 ? 99 : order;
  };
  const best = [...items].sort((a, b) => rank(a) - rank(b))[0];
  if (!best || rank(best) === 99) return null;
  const connector = String(best.connector ?? "");
  const verb =
    kind === "game"
      ? "play"
      : READ.includes(connector)
        ? kind === "audiobook"
          ? "listen"
          : "read"
        : "watch";
  return (
    <a
      className={`ds-button ${secondary ? "ds-button--secondary" : "ds-button--primary"} media-open-in`}
      href={String(best.item_link)}
      target="_blank"
      rel="noopener noreferrer external"
    >
      <Icon name={verb === "watch" ? "play" : verb === "play" ? "joystick" : "book"} size={18} />
      {t(`media:detail.openIn.${verb}`, { service: String(best.service_name ?? connector) })}
    </a>
  );
}

/** 027 (#2): watch here, in the portal's own player — the service's page stays one click away. */
function Watch({ objectId, kind }: { objectId: string; kind: string }) {
  const t = useT();
  const player = usePlayerInfo(objectId, null, PLAYABLE.includes(kind));
  const code = player.error instanceof MediaError ? player.error.code : undefined;
  const item = player.data?.item;
  const resume = item && item.resume_s > 30 && (!item.duration_s || item.resume_s < item.duration_s * 0.95);
  const reset = useResetResume(objectId);
  return (
    <div className="media-watch">
      {item ? (
        <Link className="ds-button ds-button--primary media-watch-here" to={`/media/${objectId}/watch`}>
          <Icon name="play" size={18} />
          {item.kind === "episode" && item.label
            ? t(resume ? "media:player.cta.resumeEpisode" : "media:player.cta.episode", { label: item.label })
            : t(resume ? "media:player.cta.resume" : "media:player.cta.watch")}
        </Link>
      ) : null}
      {item && resume ? (
        // compact: icon buttons beside « Resume » (their names in the tooltip and for screen readers)
        <>
          <Link
            className="ds-button ds-button--secondary media-watch-icon"
            to={`/media/${objectId}/watch?start=0`}
            aria-label={t("media:player.cta.restart")}
            title={t("media:player.cta.restart")}
          >
            <Icon name="replay" size={18} />
          </Link>
          <button
            type="button"
            className="ds-button ds-button--secondary media-watch-icon"
            disabled={reset.isPending}
            onClick={() => reset.mutate(item.external_id)}
            aria-label={t("media:player.cta.reset")}
            title={t("media:player.cta.reset")}
          >
            <Icon name="replay-10" size={18} />
          </button>
        </>
      ) : null}
      {reset.isError ? <p role="alert">{t("media:player.cta.resetFailed")}</p> : null}
      <OpenIn objectId={objectId} kind={kind} secondary={Boolean(item)} />
      {code === "media.player_unlinked" ? (
        <Link className="media-watch-hint" to="/settings/media-accounts">
          <Icon name="link" size={14} />
          {t("media:player.cta.link")}
        </Link>
      ) : null}
    </div>
  );
}

function RequestButton({
  objectId,
  kind,
  tmdb,
}: {
  objectId: string;
  kind: string;
  tmdb?: string | undefined;
}) {
  const t = useT();
  const { submit } = useRequestActions();
  if (tmdb && (kind === "movie" || kind === "series")) {
    // #4: the same form as everywhere — seasons, 4K, what it takes of my quota
    return (
      <Link className="ds-button ds-button--primary" to={`/media/discover/${kind}/${tmdb}`}>
        <Icon name="plus" size={16} />
        {t("media:detail.request")}
      </Link>
    );
  }
  return <DirectRequest objectId={objectId} submit={submit} />;
}

function DirectRequest({
  objectId,
  submit,
}: {
  objectId: string;
  submit: ReturnType<typeof useRequestActions>["submit"];
}) {
  const t = useT();
  const [key] = useState(() => `detail-${objectId}-${Date.now()}`);
  const error = submit.error instanceof MediaError ? submit.error : null;
  return (
    <div>
      <Button
        onClick={() => submit.mutate({ object_id: objectId, idempotency_key: key, is4k: false })}
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
  const metadata = useMetadata(objectId);
  const enriched = Boolean(metadata.data);
  const gallery = artworkSlides(metadata.data).length > 0; // 027: the artwork one swipes through
  const requested = Boolean(useJourney(objectId).data?.request); // 027: asked already — no second request
  if (detail.isPending) return <FunctionalState state="loading" />;
  if (detail.isError || !detail.data)
    return <FunctionalState state="unavailable" onRetry={() => detail.refetch()} />;
  const media = detail.data;
  const poster = imageUrl(media.image_id);
  return (
    <article aria-labelledby={headingId} className="media-detail">
      <PageHeader
        titleId={headingId}
        level={2}
        artwork={poster}
        art={gallery ? <Backdrop objectId={media.id} fill /> : undefined}
        title={
          <>
            {media.title} {media.year ? <span className="media-muted">({media.year})</span> : null}
          </>
        }
        context={
          <>
            {media.platform ? (
              // 027: a game's console first, plainly
              <span className="media-platform">
                <Icon name="joystick" size={14} />
                {media.platform}
              </span>
            ) : null}
            <TitleBadges media={media} />
            {t(`media:kind.${media.kind}`)}
            {media.genres.filter((g) => g !== media.platform).length
              ? ` · ${media.genres.filter((g) => g !== media.platform).join(", ")}`
              : ""}
          </>
        }
        primary={
          media.available ? (
            <Watch objectId={media.id} kind={media.kind} />
          ) : requested ? null : (
            <RequestButton objectId={media.id} kind={media.kind} tmdb={media.ids?.tmdb} />
          )
        }
      />
      <LeavingNotice objectId={media.id} />
      <RequestJourney objectId={media.id} />
      <Enrichment objectId={media.id} />
      <div className="media-sections">
        {SECTIONS.filter(
          (name) =>
            !(enriched && (name === "people" || name === "events")) &&
            !(BOOKS.includes(media.kind) && name === "people"), // a book's authors are in its facts
        ).map((name) => (
          <SectionFrame key={name} objectId={media.id} name={name} enriched={enriched} />
        ))}
      </div>
    </article>
  );
}

export default DetailPage;
