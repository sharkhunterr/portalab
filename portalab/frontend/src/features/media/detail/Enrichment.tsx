import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMeasures } from "../insights/api";

/**
 * Enriched details of a film or a series (027, metadata provider such as TMDB): the backdrop behind the
 * header, the tagline, key facts (release, runtime, rating, certification, seasons, networks…), the cast
 * with their portraits, the crew, the saga, budget and box office, studios and keywords. Images are served
 * by the portal. Nothing shows until the provider knows the title.
 */
interface Person {
  name: string;
  role: string | null;
  department: string;
  image: string | null;
}

interface Metadata {
  title: string;
  tagline: string | null;
  overview: string | null;
  genres: string[];
  release_date: string | null;
  runtime_min: number | null;
  countries: string[];
  languages: string[];
  studios: string[];
  budget: number | null;
  revenue: number | null;
  vote_average: number | null;
  vote_count: number | null;
  status: string | null;
  certification: string | null;
  collection: { id: string; name: string; poster: string | null; backdrop: string | null } | null;
  seasons: number | null;
  episodes: number | null;
  networks: string[];
  backdrop: string | null;
  people: Person[];
  keywords: string[];
  backdrops: string[];
  posters: string[];
}

const JOBS: Record<string, string> = {
  Director: "director",
  Screenplay: "screenplay",
  Writer: "writer",
  "Original Music Composer": "composer",
  Producer: "producer",
  Creator: "creator",
};

function job(t: ReturnType<typeof useT>, role: string): string {
  const key = JOBS[role];
  return key ? t(`media:enriched.job.${key}`) : role;
}

export function metadataImage(ref: string | null | undefined, size = "w500"): string | null {
  return ref ? `/api/v1/media/metadata-images?ref=${encodeURIComponent(ref)}&size=${size}` : null;
}

function normalize(raw: Partial<Metadata>): Metadata {
  const list = <T,>(value: T[] | undefined): T[] => (Array.isArray(value) ? value : []);
  return {
    title: raw.title ?? "",
    tagline: raw.tagline ?? null,
    overview: raw.overview ?? null,
    genres: list(raw.genres),
    release_date: raw.release_date ?? null,
    runtime_min: raw.runtime_min ?? null,
    countries: list(raw.countries),
    languages: list(raw.languages),
    studios: list(raw.studios),
    budget: raw.budget ?? null,
    revenue: raw.revenue ?? null,
    vote_average: raw.vote_average ?? null,
    vote_count: raw.vote_count ?? null,
    status: raw.status ?? null,
    certification: raw.certification ?? null,
    collection: raw.collection ?? null,
    seasons: raw.seasons ?? null,
    episodes: raw.episodes ?? null,
    networks: list(raw.networks),
    backdrop: raw.backdrop ?? null,
    people: list(raw.people),
    keywords: list(raw.keywords),
    backdrops: list(raw.backdrops),
    posters: list(raw.posters),
  };
}

export function useMetadata(objectId: string) {
  return useQuery({
    queryKey: ["media", objectId, "metadata"],
    retry: false,
    staleTime: 10 * 60_000,
    queryFn: async () => {
      try {
        const raw = (
          await api.GET("/api/v1/media/{object_id}/metadata", { params: { path: { object_id: objectId } } })
        ).data as Partial<Metadata> | undefined;
        return raw?.title ? normalize(raw) : null;
      } catch {
        return null; // no provider, or the title is not known yet
      }
    },
  });
}

/**
 * The artwork at the top of a title's page (027): the backdrop, then the other backdrops and posters —
 * swiped on a touch screen, with arrows and dots elsewhere; images load as they come into view.
 */
export function Backdrop({ objectId }: { objectId: string }) {
  const t = useT();
  const metadata = useMetadata(objectId);
  const strip = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const data = metadata.data;
  const slides = [
    ...[data?.backdrop, ...(data?.backdrops ?? [])]
      .filter(Boolean)
      .map((ref) => ({ ref: ref as string, poster: false })),
    ...(data?.posters ?? []).map((ref) => ({ ref, poster: true })),
  ];
  if (!slides.length) return null;
  const go = (next: number) => {
    const target = Math.max(0, Math.min(slides.length - 1, next));
    const box = strip.current;
    if (box) box.scrollTo({ left: target * box.clientWidth, behavior: "smooth" });
  };
  return (
    <div className="media-backdrop">
      <div
        ref={strip}
        className="media-backdrop__strip"
        onScroll={(event) => {
          const box = event.currentTarget;
          setIndex(Math.round(box.scrollLeft / Math.max(1, box.clientWidth)));
        }}
      >
        {slides.map((slide, i) => (
          <div key={slide.ref} className="media-backdrop__slide" data-poster={slide.poster || undefined}>
            {slide.poster ? (
              <img
                className="media-backdrop__blur"
                src={metadataImage(slide.ref, "w342") ?? ""}
                alt=""
                aria-hidden="true"
              />
            ) : null}
            <img
              src={metadataImage(slide.ref, slide.poster ? "w500" : "w1280") ?? ""}
              alt=""
              loading={i === 0 ? "eager" : "lazy"}
            />
          </div>
        ))}
      </div>
      {slides.length > 1 ? (
        <div className="media-backdrop__nav">
          <button
            type="button"
            aria-label={t("media:gallery.previous")}
            disabled={index === 0}
            onClick={() => go(index - 1)}
          >
            <Icon name="chevron-left" size={18} />
          </button>
          <span className="media-backdrop__dots">
            <span className="visually-hidden">
              {t("media:gallery.position", { index: index + 1, count: slides.length })}
            </span>
            {slides.map((slide, i) => (
              <span key={slide.ref} aria-hidden="true" data-on={i === index || undefined} />
            ))}
          </span>
          <button
            type="button"
            aria-label={t("media:gallery.next")}
            disabled={index === slides.length - 1}
            onClick={() => go(index + 1)}
          >
            <Icon name="chevron-right" size={18} />
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function Enrichment({ objectId }: { objectId: string }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const metadata = useMetadata(objectId);
  const data = metadata.data;
  if (!data) return null;
  const cast = data.people.filter((p) => p.department === "cast");
  const crew = data.people.filter((p) => p.department !== "cast");
  const facts = [
    data.release_date
      ? { key: "release", icon: "calendar", value: format.date(data.release_date, "long") }
      : null,
    data.runtime_min
      ? { key: "runtime", icon: "clock", value: measures.duration(data.runtime_min * 60) }
      : null,
    data.vote_average
      ? {
          key: "rating",
          icon: "star",
          value: `${data.vote_average.toFixed(1)}/10${data.vote_count ? ` · ${t("media:enriched.votes", { count: data.vote_count })}` : ""}`,
        }
      : null,
    data.certification ? { key: "certification", icon: "shield", value: data.certification } : null,
    data.seasons
      ? { key: "seasons", icon: "list", value: t("media:enriched.seasons", { count: data.seasons }) }
      : null,
    data.episodes
      ? { key: "episodes", icon: "film", value: t("media:enriched.episodes", { count: data.episodes }) }
      : null,
    data.networks.length ? { key: "networks", icon: "globe", value: data.networks.join(", ") } : null,
    data.countries.length ? { key: "countries", icon: "compass", value: data.countries.join(", ") } : null,
  ].filter((f) => f !== null);
  const profit = data.budget && data.revenue ? data.revenue / data.budget : null;
  return (
    <section className="media-enriched" aria-label={t("media:enriched.title")}>
      {data.tagline ? <p className="media-enriched__tagline">« {data.tagline} »</p> : null}
      {facts.length ? (
        <ul className="media-enriched__facts">
          {facts.map((fact) => (
            <li key={fact.key}>
              <Icon name={fact.icon} size={16} />
              {fact.value}
            </li>
          ))}
        </ul>
      ) : null}
      {data.overview ? <p className="media-enriched__overview">{data.overview}</p> : null}
      {data.genres.length ? (
        <ul className="media-enriched__chips" aria-label={t("media:enriched.genres")}>
          {data.genres.map((genre) => (
            <li key={genre}>{genre}</li>
          ))}
        </ul>
      ) : null}
      {cast.length ? (
        <div className="media-enriched__block">
          <h3>{t("media:enriched.cast")}</h3>
          <ul className="media-enriched__cast">
            {cast.map((person) => {
              const src = metadataImage(person.image, "w185");
              return (
                <li key={`${person.name}-${person.role ?? ""}`}>
                  <span className="media-enriched__portrait">
                    {src ? <img src={src} alt="" loading="lazy" /> : <Icon name="user" size={28} />}
                  </span>
                  <strong>{person.name}</strong>
                  {person.role ? <span className="media-muted">{person.role}</span> : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      <div className="media-enriched__grid">
        {crew.length ? (
          <div className="media-enriched__block">
            <h3>{t("media:enriched.crew")}</h3>
            <dl className="media-enriched__pairs">
              {crew.slice(0, 8).map((person) => (
                <div key={`${person.name}-${person.role ?? ""}`}>
                  <dt>{person.role ? job(t, person.role) : ""}</dt>
                  <dd>{person.name}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
        {data.collection ? (
          <div className="media-enriched__block media-enriched__saga">
            <h3>{t("media:enriched.saga")}</h3>
            {metadataImage(data.collection.poster, "w185") ? (
              <img src={metadataImage(data.collection.poster, "w185") ?? ""} alt="" loading="lazy" />
            ) : null}
            <p>{data.collection.name}</p>
          </div>
        ) : null}
        {data.budget || data.revenue ? (
          <div className="media-enriched__block">
            <h3>{t("media:enriched.money")}</h3>
            <dl className="media-enriched__pairs">
              {data.budget ? (
                <div>
                  <dt>{t("media:enriched.budget")}</dt>
                  <dd>{measures.money(data.budget)}</dd>
                </div>
              ) : null}
              {data.revenue ? (
                <div>
                  <dt>{t("media:enriched.revenue")}</dt>
                  <dd>{measures.money(data.revenue)}</dd>
                </div>
              ) : null}
              {profit ? (
                <div>
                  <dt>{t("media:enriched.multiple")}</dt>
                  <dd data-tone={profit >= 1 ? "ok" : "bad"}>× {profit.toFixed(1)}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}
        {data.studios.length || data.languages.length ? (
          <div className="media-enriched__block">
            <h3>{t("media:enriched.production")}</h3>
            <dl className="media-enriched__pairs">
              {data.studios.length ? (
                <div>
                  <dt>{t("media:enriched.studios")}</dt>
                  <dd>{data.studios.slice(0, 4).join(", ")}</dd>
                </div>
              ) : null}
              {data.languages.length ? (
                <div>
                  <dt>{t("media:enriched.languages")}</dt>
                  <dd>{data.languages.join(", ")}</dd>
                </div>
              ) : null}
              {data.status ? (
                <div>
                  <dt>{t("media:enriched.status")}</dt>
                  <dd>{data.status}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}
      </div>
      {data.keywords.length ? (
        <ul
          className="media-enriched__chips media-enriched__chips--quiet"
          aria-label={t("media:enriched.keywords")}
        >
          {data.keywords.map((keyword) => (
            <li key={keyword}>#{keyword}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
