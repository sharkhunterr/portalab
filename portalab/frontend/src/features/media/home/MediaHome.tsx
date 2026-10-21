import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { Skeleton } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { imageUrl, type MediaCard, type ShelfName, useNowPlaying, useShelf } from "../api";
import { metadataImage } from "../detail/Enrichment";
import { DiscoverShelves } from "../discover/DiscoverShelves";
import { LeavingBadge } from "../discover/StatusBadge";
import { KIND_ICONS, MediaGrid, Poster } from "../MediaGrid";
import { useRadio } from "../radio/api";
import { RadioCard } from "../radio/RadioCard";
import "../media.css";

/** A title from the services' history (027): in the library (``id``) or not (the provider's poster). */
interface JournalItem {
  id: string | null;
  title: string;
  subtitle?: string | null;
  kind: string;
  progress: number | null;
  image_id?: string | null;
  poster_ref?: string | null;
  route?: string | null;
}

function useJournal() {
  return useQuery({
    queryKey: ["media", "journal"],
    queryFn: async () =>
      ((await api.GET("/api/v1/me/media/journal")).data ?? { continue: [], recent: [] }) as {
        continue: JournalItem[];
        recent: JournalItem[];
      },
    staleTime: 60_000,
  });
}

const KINDS = ["movie", "series", "book", "audiobook", "game", "album"];

function JournalRail({
  items,
  label,
  progress,
}: {
  items: JournalItem[];
  label: string;
  progress?: boolean;
}) {
  const t = useT();
  return (
    <ul className="media-rail" aria-label={label}>
      {items.map((item) => {
        const src = imageUrl(item.image_id) ?? metadataImage(item.poster_ref, "w342");
        const percent = item.progress === null ? null : Math.round(item.progress * 100);
        const body = (
          <>
            <span className="media-card__frame">
              <Poster src={src} kind={item.kind} />
              <span className="media-card__kind" title={t(`media:kind.${item.kind}`)}>
                <Icon name={KIND_ICONS[item.kind] ?? "film"} size={12} />
              </span>
              {progress && percent !== null ? (
                <span
                  className="media-card__progress"
                  role="progressbar"
                  aria-valuenow={percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={item.title}
                >
                  <span style={{ inlineSize: `${percent}%` }} />
                </span>
              ) : null}
            </span>
            <span className="media-card__title">{item.title}</span>
            <span className="media-card__meta">{item.subtitle || t(`media:kind.${item.kind}`)}</span>
          </>
        );
        return (
          <li key={`${item.kind}:${item.id ?? item.title}:${item.subtitle ?? ""}`} className="media-card">
            {item.id ? (
              <Link to={`/media/${item.id}`} className="media-card__link">
                {body}
              </Link>
            ) : (
              <span className="media-card__link">{body}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Row({
  icon,
  title,
  more,
  children,
}: {
  icon: string;
  title: string;
  more?: { to: string; label: string } | undefined;
  children: React.ReactNode;
}) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className="media-row">
      <header className="media-row__head">
        <h3 id={headingId}>
          <Icon name={icon} size={18} />
          {title}
        </h3>
        {more ? (
          <Link to={more.to} className="media-row__more">
            {more.label}
            <Icon name="chevron-right" size={14} />
          </Link>
        ) : null}
      </header>
      {children}
    </section>
  );
}

/** A discovery shelf: shown only when it has something (an empty shelf is not a section). */
function Shelf({ name, icon }: { name: ShelfName; icon: string }) {
  const t = useT();
  const format = useFormat();
  const shelf = useShelf(name);
  // issue 110: the day it goes, as a badge on the poster (like « Available »)
  const leaving = (item: MediaCard) => (
    <LeavingBadge
      label={
        item.at
          ? t("media:widget.leaving.on", { when: format.relative((Date.parse(item.at) - Date.now()) / 1000) })
          : t("media:widget.leaving.someday")
      }
    />
  );
  const note = (item: MediaCard) => {
    if (!item.at || name === "leaving") return null;
    const when =
      name === "new"
        ? format.relative((Date.parse(item.at) - Date.now()) / 1000)
        : format.date(`${item.at.slice(0, 10)}T12:00:00Z`, "medium");
    return item.episode ? `${item.episode} · ${when}` : when;
  };
  if (shelf.isError) return null;
  if (shelf.isPending) {
    return (
      <Row icon={icon} title={t(`media:shelf.${name}`)}>
        <Skeleton shape="tile" count={5} label={t(`media:shelf.${name}`)} />
      </Row>
    );
  }
  if (!shelf.data.items.length) return null;
  return (
    <Row
      icon={icon}
      title={t(`media:shelf.${name}`)}
      more={name === "leaving" ? undefined : { to: "/media/browse", label: t("media:home.seeAll") }}
    >
      <MediaGrid
        items={shelf.data.items}
        label={t(`media:shelf.${name}`)}
        rail
        note={note}
        badge={name === "leaving" ? leaving : undefined}
      />
    </Row>
  );
}

function NowPlaying() {
  const t = useT();
  const sessions = useNowPlaying();
  const live = sessions.data ?? [];
  if (!live.length) return null;
  return (
    <ul className="media-live" aria-label={t("media:home.nowPlaying")}>
      {live.map((s) => {
        const percent = s.duration_s ? Math.round(((s.position_s ?? 0) / s.duration_s) * 100) : null;
        const label = t(`media:kind.${s.kind}`);
        return (
          <li key={s.session} className="media-live__item">
            <span className="media-live__pulse" aria-hidden="true" />
            <Icon name={KIND_ICONS[s.kind] ?? "play"} size={18} />
            {s.object_id ? <Link to={`/media/${s.object_id}`}>{label}</Link> : <span>{label}</span>}
            <span className="media-live__state">{t(`media:home.state.${s.state}`)}</span>
            {percent !== null ? (
              <span className="media-live__bar" aria-hidden="true">
                <span style={{ inlineSize: `${percent}%` }} />
              </span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function Hero() {
  const t = useT();
  const fresh = useShelf("new");
  const backdrop = (fresh.data?.items ?? []).filter((i) => i.image_id).slice(0, 5);
  return (
    <section className="media-hero" aria-label={t("media:home.title")}>
      <span className="media-hero__wall" aria-hidden="true">
        {backdrop.map((item) => (
          <img key={item.id} src={imageUrl(item.image_id) ?? ""} alt="" />
        ))}
      </span>
      <PageHeader
        level={2}
        title={t("media:home.hello")}
        context={t("media:home.pitch")}
        secondary={
          <Link className="ds-button ds-button--secondary" to="/media/discover">
            <Icon name="plus" size={16} />
            {t("media:home.request")}
          </Link>
        }
        primary={
          <Link className="ds-button ds-button--primary" to="/media/browse">
            <Icon name="search" size={16} />
            {t("media:home.browse")}
          </Link>
        }
      />
      <NowPlaying />
    </section>
  );
}

/**
 * Media home (spec 024 T024/T028; 027 redesign): a welcoming banner with what is playing, then rows that
 * scroll sideways — what I am in the middle of and what I opened lately (from the services' history:
 * Plex/Tautulli, Grimmory…), the library's new arrivals, trends and recommendations, and a way in by
 * kind. A row with nothing to show is left out instead of saying so.
 */
/** Issue 168: the homelab's radio, when one is connected — listen, ask its DJ, its own page. */
function RadioRow() {
  const t = useT();
  const radio = useRadio();
  if (!radio.data?.available) return null;
  return (
    <Row
      icon="radio"
      title={t("media:radio.title")}
      more={{ to: "/media/radio", label: t("media:radio.open") }}
    >
      <div className="media-radio">
        <RadioCard radio={radio.data} />
      </div>
    </Row>
  );
}

export function MediaHome() {
  const t = useT();
  const journal = useJournal();
  const going = journal.data?.continue ?? [];
  const lately = (journal.data?.recent ?? []).filter(
    (item) => !going.some((g) => g.title === item.title && g.kind === item.kind),
  );
  return (
    <div className="media-home">
      <Hero />
      {journal.isError ? <FunctionalState state="unavailable" onRetry={() => journal.refetch()} /> : null}
      {going.length ? (
        <Row icon="play" title={t("media:shelf.continue")}>
          <JournalRail items={going} label={t("media:shelf.continue")} progress />
        </Row>
      ) : null}
      <RadioRow />
      <Shelf name="new" icon="sparkles" />
      <Shelf name="released" icon="clapperboard" />
      {/* issue 110: what the library's cleanup will delete — save one from its page */}
      <Shelf name="leaving" icon="trash" />
      {lately.length ? (
        <Row
          icon="clock"
          title={t("media:shelf.recent")}
          more={{ to: "/media/insights", label: t("media:home.myStats") }}
        >
          <JournalRail items={lately} label={t("media:shelf.recent")} />
        </Row>
      ) : null}
      <Shelf name="trending" icon="trending" />
      <Shelf name="recommended" icon="heart" />
      {/* #4: what one can ask for, like Seerr's home */}
      <DiscoverShelves />
      <Row icon="list" title={t("media:home.byKind")}>
        <ul className="media-kinds">
          {KINDS.map((kind) => (
            <li key={kind}>
              <Link to={`/media/browse?kind=${kind}`} data-kind={kind}>
                <Icon name={KIND_ICONS[kind] ?? "film"} size={22} />
                {t(`media:kind.${kind}`)}
              </Link>
            </li>
          ))}
        </ul>
      </Row>
    </div>
  );
}

export default MediaHome;
