import { type ReactNode, useId, useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useAssistantPage } from "../../ai/pageContext";
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
import { useCollectsCards } from "../../cards/collects";
import { WorkCollection } from "../../cards/WorkCollection";
import { ExternalNews } from "../../news/ExternalNews";
import { PluginSlot } from "../../plugins/slots/PluginSlot";
import { MediaTickets, MediaTicketsBadge } from "../../support/tickets/MediaTickets";
import { ReportMediaProblem } from "../../support/tickets/ReportMedia";
import { useListenInfo, useReadInfo } from "../books/api";
import { useDiscoverTitle } from "../discover/api";
import { RequestDialog } from "../discover/RequestDialog";
import { FollowButton } from "../feed/FollowButton";
import { useMeasures } from "../insights/api";
import { openBook, useListen } from "../listen/store";
import { usePlayerInfo, useResetResume } from "../player/api";
import { TasteButtons } from "../taste/TasteButtons";
import { BookView } from "./BookView";
import { EnrichedView, Enrichment, metadataImage, normalize, useMetadata } from "./Enrichment";
import { RequestJourney, useJourney } from "./Journey";
import { LeavingNotice } from "./Leaving";
import { ReviewButton, Reviews } from "./Reviews";
import { TitleHero } from "./TitleHero";

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

const BOOKS = ["book", "audiobook"];

/** 027: a game's facts (RomM): its platform, publisher and studios, release date, franchises and modes. */
/** Issue 351: how long a game takes by play style (HowLongToBeat, through RomM), as RomM's page shows it. */
const PLAY_STYLES = ["main_story", "main_plus_extra", "completionist", "all_styles"] as const;
export type PlayTimes = Partial<
  Record<(typeof PLAY_STYLES)[number], { seconds: number; players?: number | null }>
>;

export function PlayTimesFacts({ times }: { times: PlayTimes }) {
  const t = useT();
  const measures = useMeasures();
  const styles = PLAY_STYLES.filter((style) => times[style]?.seconds);
  if (!styles.length) return null;
  return (
    <section className="media-playtimes" aria-labelledby="media-playtimes-title">
      <h3 id="media-playtimes-title">
        <Icon name="clock" size={16} />
        {t("media:facts.playTimes")}
      </h3>
      <dl>
        {styles.map((style) => {
          const time = times[style];
          return (
            <div key={style}>
              <dt>{t(`media:facts.playTime.${style}`)}</dt>
              <dd>
                <strong>{measures.duration(Number(time?.seconds))}</strong>
                {typeof time?.players === "number" ? (
                  <span>{t("media:facts.playTimePlayers", { count: time.players })}</span>
                ) : null}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}

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
  const times = (data.play_times && typeof data.play_times === "object" ? data.play_times : {}) as PlayTimes;
  if (!rows.length && !tags.length && !Object.keys(times).length) return null;
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
      <PlayTimesFacts times={times} />
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

interface JourneyStep {
  key: string;
  status: string;
  detail?: string;
  cinema?: string;
  digital?: string;
  physical?: string;
  first_aired?: string;
  items?: Array<{ progress?: number | null }>;
}
interface Journey {
  request?: { state?: string } | null;
  steps?: JourneyStep[];
}
interface Stage {
  key: string;
  progress?: number;
  date?: string | undefined;
}

const STAGE_BADGE_TONE: Record<string, string> = {
  available: "available",
  downloading: "downloading",
  importing: "downloading",
  import_blocked: "unavailable",
  declined: "unavailable",
  failed: "unavailable",
};
const STAGE_ICONS: Record<string, string> = {
  available: "check",
  pending: "hourglass",
  awaiting_release: "calendar",
  searching: "search",
  downloading: "package",
  importing: "package",
  import_blocked: "blocked",
  declined: "blocked",
  failed: "blocked",
};

/** Issue 172: where a requested title stands, from its journey — the first step not done yet. */
export function stageOf(journey: Journey | undefined): Stage | null {
  const steps = journey?.steps ?? [];
  const at = steps.find((step) => step.status !== "done");
  if (at) {
    if (at.key === "requested" || at.key === "approved")
      return at.status === "failed"
        ? { key: at.detail === "cancelled" ? "cancelled" : at.detail === "failed" ? "failed" : "declined" }
        : { key: "pending" };
    if (at.key === "released")
      return { key: "awaiting_release", date: at.cinema ?? at.digital ?? at.physical ?? at.first_aired };
    if (at.key === "searched") return { key: "searching" };
    if (at.key === "downloading") {
      const progress = at.items?.find((item) => typeof item.progress === "number")?.progress;
      return progress == null ? { key: "downloading" } : { key: "downloading", progress };
    }
    if (at.key === "imported") return { key: at.status === "blocked" ? "import_blocked" : "importing" };
    if (at.key === "available") return { key: "importing" };
  }
  const state = journey?.request?.state; // no journey to tell: the request's own word, never « downloading »
  if (state === "pending" || state === "approved") return { key: "pending" };
  if (state === "processing") return { key: "searching" };
  if (state === "declined" || state === "failed" || state === "cancelled") return { key: state };
  return null;
}

/** 027 (#22): up top — is it here (or on its way), and did I see it already (or how far I am). */
function TitleBadges({ media }: { media: { id: string; kind: string; available: boolean } }) {
  const t = useT();
  const format = useFormat();
  const journey = useJourney(media.id).data as Journey | undefined;
  const player = usePlayerInfo(media.id, null, media.available && PLAYABLE.includes(media.kind)).data?.item;
  const viewing = (useSection(media.id, "viewing").data?.data ?? {}) as Data;
  // issue 172: the badge says the journey's own stage (the step it is at), never the request's raw state —
  // a request « processing » for a film not out yet is « Out on … », not « Downloading »
  const stage = media.available ? { key: "available" } : stageOf(journey);
  const availability = stage ? (STAGE_BADGE_TONE[stage.key] ?? "requested") : "unavailable";
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
      {/* issue 355: « Available » goes without saying beside « Watch » (and the journey's card tells since
          when); a title on its way or missing still says so */}
      {stage?.key === "available" ? null : (
        <span className="media-badge" data-tone={availability}>
          <Icon name={STAGE_ICONS[stage?.key ?? ""] ?? "blocked"} size={14} />
          {stage
            ? t(`media:myRequests.stage.${stage.key}`, {
                percent: Math.round((stage.progress ?? 0) * 100),
                date: stage.date ? format.date(stage.date.slice(0, 10), "medium") : "",
              })
            : t("media:badge.unavailable")}
        </span>
      )}
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
      {/* issue 354: the problems reported on it and still open */}
      <MediaTicketsBadge mediaId={media.id} />
      {seen ? (
        <span className="media-badge" data-tone="seen">
          <Icon name="eye" size={14} />
          {t(`media:badge.seen.${SEEN_WORD[media.kind] ?? "watched"}`)}
        </span>
      ) : null}
    </span>
  );
}

/** #4: every request for this title — mine with what they say (seasons, 4K, why one was declined) and a
 * way to cancel it while it waits; the others as « a member ». */
function RequestsBody({ data }: { data: Data }) {
  const t = useT();
  const format = useFormat();
  const { cancel } = useRequestActions();
  const items = list(data.requests).length ? list(data.requests) : list(data.mine);
  return (
    <>
      <p className="media-muted">{t("media:detail.openRequests", { count: Number(data.open_total ?? 0) })}</p>
      <ul className="media-requests">
        {items.map((r) => {
          const seasons = Array.isArray(r.seasons) ? (r.seasons as number[]) : null;
          return (
            <li key={String(r.id)} data-mine={r.mine ? true : undefined}>
              <span className="media-badge" data-tone={String(r.state)}>
                {t(`media:requests.state.${String(r.state)}`)}
              </span>
              <span className="media-requests__who">
                {r.mine ? t("media:detail.requestMine") : t("media:detail.requestOther")}
                {r.requested_at
                  ? ` · ${format.relative((Date.parse(String(r.requested_at)) - Date.now()) / 1000)}`
                  : ""}
                {seasons?.length ? ` · ${t("media:moderation.seasons", { list: seasons.join(", ") })}` : ""}
                {r.is4k ? " · 4K" : ""}
              </span>
              {r.reason ? <span className="media-requests__reason">« {String(r.reason)} »</span> : null}
              {r.cancellable ? (
                <button
                  type="button"
                  className="ds-button ds-button--ghost media-requests__cancel"
                  disabled={cancel.isPending}
                  onClick={() => cancel.mutate(String(r.id))}
                >
                  {t("media:detail.cancelRequest")}
                </button>
              ) : null}
            </li>
          );
        })}
      </ul>
    </>
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
          {data.overview && !enriched && !BOOKS.includes(String(data.kind)) ? (
            <p>{String(data.overview)}</p>
          ) : null}
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
      return <RequestsBody data={data} />;
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
        // #92: a book's summary and facts are laid out like a film's (BookView), above the sections
        (Boolean(data.overview) && !enriched && !BOOKS.includes(String(data.kind))) ||
        list(data.children).length > 0 ||
        (data.kind === "game" &&
          Boolean(data.platform || data.publisher || data.people || data.released || data.play_times))
      );
    case "history":
      return list(data.mine).length > 0 || list(data.concerned_users).length > 0;
    case "requests":
      return Number(data.open_total ?? 0) > 0 || list(data.requests).length > 0 || list(data.mine).length > 0;
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

/** 027 (#2), #20, #21: watch, listen or read here — the service's page stays one click away. */
function Watch({
  objectId,
  kind,
  title,
  image,
}: {
  objectId: string;
  kind: string;
  title: string;
  image: string | null | undefined;
}) {
  if (kind === "audiobook") return <Listen objectId={objectId} title={title} image={image ?? null} />;
  if (kind === "book") return <Read objectId={objectId} />;
  return <WatchVideo objectId={objectId} kind={kind} />;
}

/** #20: listen here — the audiobook plays in the portal's bar and carries on while browsing. */
function Listen({ objectId, title, image }: { objectId: string; title: string; image: string | null }) {
  const t = useT();
  const format = useFormat();
  const info = useListenInfo(objectId, true);
  const listen = useListen();
  const resume = info.data?.resume;
  const share = resume?.percent ?? 0;
  const here = listen.objectId === objectId;
  const started = Boolean(resume && resume.position_s > 30 && share < 0.99);
  return (
    <div className="media-watch">
      {info.data ? (
        <>
          <button
            type="button"
            className="ds-button ds-button--primary media-watch-here"
            onClick={() => void openBook(objectId, { title, image })}
          >
            <Icon name={here && listen.playing ? "headphones" : "play"} size={18} />
            {here && listen.playing
              ? t("media:listen.cta.playing")
              : started
                ? t("media:listen.cta.resume", { percent: format.percent(share) })
                : t("media:listen.cta.listen")}
          </button>
          {started ? (
            <button
              type="button"
              className="ds-button ds-button--secondary media-watch-icon"
              onClick={() => void openBook(objectId, { title, image, at: 0 })}
              aria-label={t("media:player.cta.restart")}
              title={t("media:player.cta.restart")}
            >
              <Icon name="replay" size={18} />
            </button>
          ) : null}
        </>
      ) : null}
      <OpenIn objectId={objectId} kind="audiobook" secondary={Boolean(info.data)} />
    </div>
  );
}

/** #21: read here — the reader opens over the whole window (a page of its own, entered by a full load). */
function Read({ objectId }: { objectId: string }) {
  const t = useT();
  const format = useFormat();
  const info = useReadInfo(objectId);
  const readable = info.data?.book.formats.filter((f) => ["epub", "pdf", "cbx"].includes(f.format)) ?? [];
  const best = [...(info.data?.resume ?? [])].sort((a, b) => b.percent - a.percent)[0];
  const started = Boolean(best && best.percent > 0.005 && best.percent < 0.995);
  return (
    <div className="media-watch">
      {readable.length ? (
        <a className="ds-button ds-button--primary media-watch-here" href={`/media/${objectId}/read`}>
          <Icon name="book-open" size={18} />
          {started && best
            ? t("media:reader.cta.resume", { percent: format.percent(best.percent) })
            : t("media:reader.cta.read")}
        </a>
      ) : null}
      <OpenIn objectId={objectId} kind="book" secondary={readable.length > 0} />
    </div>
  );
}

/** 027 (#2): watch here, in the portal's own player — the service's page stays one click away. */
function WatchVideo({ objectId, kind }: { objectId: string; kind: string }) {
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
  const { submit } = useRequestActions();
  if (tmdb && (kind === "movie" || kind === "series")) {
    return <AskHere objectId={objectId} kind={kind} tmdb={tmdb} submit={submit} />;
  }
  return <DirectRequest objectId={objectId} submit={submit} />;
}

/** #4: the same form as everywhere — a series' missing seasons, 4K, what it takes of my quota — here. */
function AskHere({
  objectId,
  kind,
  tmdb,
  submit,
}: {
  objectId: string;
  kind: "movie" | "series";
  tmdb: string;
  submit: ReturnType<typeof useRequestActions>["submit"];
}) {
  const t = useT();
  const details = useDiscoverTitle(kind, tmdb);
  if (details.isError) return <DirectRequest objectId={objectId} submit={submit} />;
  if (!details.data) return null;
  const data = details.data;
  return (
    <RequestDialog
      target={{
        tmdb_id: data.tmdb_id,
        kind: data.kind,
        title: data.title,
        ids: data.ids,
        seasons: data.seasons,
        four_k: data.four_k,
      }}
      trigger={
        <Button>
          <Icon name="plus" size={16} />
          {t("media:detail.request")}
        </Button>
      }
    />
  );
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

const TASTED = ["movie", "series", "season", "episode", "book", "audiobook", "game"];

export function DetailPage() {
  const t = useT();
  const format = useFormat();
  const collects = useCollectsCards(); // issue 243: its cards, for a member who collects them
  const measures = useMeasures();
  const { objectId = "" } = useParams();
  const headingId = useId();
  const detail = useMediaDetail(objectId);
  // with enriched details (TMDB), the cast and the technical timeline would only repeat or distract
  const metadata = useMetadata(objectId);
  const known = detail.data;
  const seerrKind =
    known && (known.kind === "movie" || known.kind === "series") && known.ids?.tmdb ? known.kind : null;
  const asked = useDiscoverTitle(
    seerrKind ?? "movie",
    known?.ids?.tmdb ?? "",
    Boolean(seerrKind) && !metadata.data && !metadata.isPending,
  );
  const requested = Boolean(useJourney(objectId).data?.request); // 027: asked already — no second request
  const info = useSection(objectId, "info").data?.data as Data | undefined;
  // issue 171: « this title » for the assistant
  useAssistantPage(
    // the name and kind too: without them the model cannot tell whether a question is about this page
    known ? `media id=${known.id} « ${known.title} » (${known.kind})` : null,
    known ? `${known.title}${known.year ? ` (${known.year})` : ""} · ${t(`media:kind.${known.kind}`)}` : null,
  );
  if (detail.isPending) return <FunctionalState state="loading" />;
  if (detail.isError || !detail.data)
    return <FunctionalState state="unavailable" onRetry={() => detail.refetch()} />;
  const media = detail.data;
  const poster = imageUrl(media.image_id);
  // a title just asked for has no enriched details yet: the request service's stand in meanwhile
  const stand = !metadata.data && seerrKind ? asked.data : undefined;
  const fallback = stand?.metadata && Object.keys(stand.metadata).length ? stand : undefined;
  const details =
    metadata.data ?? (fallback ? normalize({ ...fallback.metadata, title: media.title }) : undefined);
  const enriched = Boolean(details);
  const shownPoster = poster ?? metadataImage(metadata.data?.posters?.[0] ?? fallback?.poster, "w342");
  // issue 354: what the dialogs about this title say under its name
  const dialogFacts = [media.year ? String(media.year) : null, t(`media:kind.${media.kind}`)]
    .filter(Boolean)
    .join(" · ");
  // #92: a book's head tells its length and readers' rating, as a film's does (its genres come below)
  const bookFacts =
    BOOKS.includes(media.kind) && info
      ? [
          info.duration_s ? measures.duration(Number(info.duration_s)) : null,
          info.pages ? t("media:facts.pageCount", { count: Number(info.pages) }) : null,
          info.rating ? `★ ${format.number(Math.round(Number(info.rating) * 10) / 10)}` : null,
        ].filter((fact) => fact !== null)
      : [];
  return (
    <article aria-labelledby={headingId} className="media-detail">
      {/* #4: the same head as a title to ask for — backdrop, poster, facts, badges, actions */}
      <TitleHero
        headingId={headingId}
        level={2}
        title={media.title}
        kind={media.kind}
        poster={shownPoster}
        backdrop={metadataImage(details?.backdrop ?? details?.backdrops?.[0] ?? fallback?.backdrop, "w1280")}
        facts={[
          media.year ? String(media.year) : null,
          media.platform ?? null,
          t(`media:kind.${media.kind}`),
          metadata.data?.runtime_min ? measures.duration(metadata.data.runtime_min * 60) : null,
          metadata.data?.vote_average
            ? `★ ${format.number(Math.round(metadata.data.vote_average * 10) / 10)}`
            : null,
          bookFacts.length
            ? null
            : !enriched && media.genres.length
              ? media.genres.filter((g) => g !== media.platform).join(", ")
              : null,
          ...bookFacts,
        ]}
        badges={<TitleBadges media={media} />}
        primary={
          media.available ? (
            <Watch objectId={media.id} kind={media.kind} title={media.title} image={media.image_id} />
          ) : requested ? null : (
            <RequestButton objectId={media.id} kind={media.kind} tmdb={media.ids?.tmdb} />
          )
        }
      >
        {/* issue 355: one bar of small actions under the title — the rest is in dialogs */}
        <div className="media-actions">
          {/* issue 190: what I think of it — it shapes my recommendations */}
          {TASTED.includes(media.kind) ? (
            <TasteButtons objectId={media.id} title={media.title} compact />
          ) : null}
          {/* issue 355: my review (a rating, a few words), in a dialog */}
          <ReviewButton objectId={media.id} title={media.title} poster={shownPoster} facts={dialogFacts} />
          {/* issue 299: a series followed brings its new episodes into « Mon fil » */}
          {media.kind === "series" ? <FollowButton kind="title" value={media.id} name={media.title} /> : null}
          {/* 030: what plugins add to a title's page (« + Playlist »…), drawn by Portalab */}
          <PluginSlot name="media.actions" params={{ item: media.id }} />
          {/* issue 354: a problem with it (subtitles, language, a cut file…) — a ticket about this media */}
          <ReportMediaProblem
            objectId={media.id}
            title={media.title}
            poster={shownPoster}
            facts={dialogFacts}
          />
        </div>
      </TitleHero>
      <LeavingNotice objectId={media.id} title={media.title} />
      <RequestJourney objectId={media.id} title={media.title} />
      {/* issue 299: what the news sources say of it */}
      <ExternalNews heading={t("news:external.aboutTitle")} asked={{ title: [media.id] }} />
      {metadata.data ? (
        <Enrichment objectId={media.id} />
      ) : details ? (
        <EnrichedView data={details} />
      ) : BOOKS.includes(media.kind) ? (
        <BookView objectId={media.id} genres={media.genres} />
      ) : null}
      {collects && (media.kind === "movie" || media.kind === "series") ? (
        <WorkCollection objectId={media.id} />
      ) : null}
      {/* issue 355: what the members thought of it — and mine, once seen, read or played */}
      <Reviews objectId={media.id} title={media.title} poster={shownPoster} facts={dialogFacts} />
      <div className="media-sections">
        {SECTIONS.filter(
          (name) =>
            !(enriched && (name === "people" || name === "events")) &&
            !(BOOKS.includes(media.kind) && name === "people"), // a book's authors are in its facts
        ).map((name) => (
          <SectionFrame key={name} objectId={media.id} name={name} enriched={enriched} />
        ))}
      </div>
      {/* issue 354: the tickets about it — open, and the closed ones on demand */}
      <MediaTickets mediaId={media.id} />
    </article>
  );
}

export default DetailPage;
