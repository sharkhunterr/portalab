import { useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ExternalNews } from "../../news/ExternalNews";
import { imageUrl, MediaError, type Person, usePerson } from "../api";
import { metadataImage } from "../detail/Enrichment";
import { RequestDialog } from "../discover/RequestDialog";
import { PosterBadge, StatusBadge } from "../discover/StatusBadge";
import { FollowButton } from "../feed/FollowButton";
import { KIND_ICONS, MediaGrid, Poster } from "../MediaGrid";
import "../media.css";
import { PosterTickets } from "../../support/tickets/MediaTickets";

/**
 * #92 — a person's page: an actor's, a director's, an author's, a narrator's. What the configured
 * services know of them (TMDB, Seerr, Jellyfin, Grimmory… whichever there are): portrait, birth,
 * biography, what they are known for; their titles in the library, by role; and their whole filmography,
 * each title told available, asked for, not available or to ask for. Reached from the search (its
 * « People » section) and from a title's cast and crew.
 */
type Credit = Person["filmography"][number];
type Filter = "all" | "available" | "missing";

/** A department in words (« Réalisation »), or as the service names it when unknown. */
function department(t: ReturnType<typeof useT>, value: string): string {
  const key = `media:person.department.${value.toLowerCase()}`;
  const label = t(key);
  return label === key || label === key.split(":")[1] ? value : label;
}

function day(value: string): string {
  return `${value.slice(0, 10)}T12:00:00`; // a calendar day: noon never crosses a date line
}

export function PersonPage() {
  const t = useT();
  const headingId = useId();
  const { name = "" } = useParams();
  const person = usePerson(name);
  if (person.isPending) return <FunctionalState state="loading" />;
  if (person.isError || !person.data) {
    const missing = person.error instanceof MediaError && person.error.status === 404;
    return (
      <section aria-labelledby={headingId} className="media-person">
        <PageHeader titleId={headingId} level={2} icon="user" title={name} />
        {missing ? (
          <p className="ds-panel">{t("media:person.notFound")}</p>
        ) : (
          <FunctionalState state="unavailable" onRetry={() => person.refetch()} />
        )}
        <Link className="ds-button ds-button--secondary" to={`/search?q=${encodeURIComponent(name)}`}>
          {t("media:person.back")}
        </Link>
      </section>
    );
  }
  return <PersonView headingId={headingId} data={person.data} />;
}

function PersonView({ headingId, data }: { headingId: string; data: Person }) {
  const t = useT();
  const format = useFormat();
  const profile = data.profile;
  const [open, setOpen] = useState(false);
  const [broken, setBroken] = useState(false);
  const facts = [
    profile?.birthday
      ? t("media:person.born", {
          date: format.date(day(profile.birthday), "long"),
          place: profile.place_of_birth || "none",
        })
      : null,
    profile?.deathday ? t("media:person.died", { date: format.date(day(profile.deathday), "long") }) : null,
  ].filter(Boolean) as string[];
  const counts = data.counts ?? {};
  const stats = [
    {
      key: "library",
      value: Math.max(
        data.titles,
        (counts.available ?? 0) + (counts.requested ?? 0) + (counts.unavailable ?? 0),
      ),
      tone: "accent",
    },
    { key: "available", value: counts.available ?? 0, tone: "ok" },
    { key: "requested", value: counts.requested ?? 0, tone: "warn" },
    { key: "missing", value: counts.missing ?? 0, tone: "neutral" },
    { key: "absent", value: counts.absent ?? 0, tone: "neutral" }, // issue 362: their books not there
  ].filter((stat) => stat.key === "library" || stat.value > 0);
  const known = profile?.known_for ? department(t, profile.known_for) : null;
  // an author, a narrator: their books first; what the film services know of them after
  const books = data.roles.length > 0 && data.roles.every((role) => role === "author" || role === "narrator");
  const knownFor = data.known_for?.length ? (
    <section className="media-row media-person__section">
      <h3>{t("media:person.knownFor")}</h3>
      <ul className="media-rail">
        {data.known_for.map((credit) => (
          <KnownCard key={`${credit.kind}:${credit.tmdb_id}`} credit={credit} askable={data.askable} />
        ))}
      </ul>
    </section>
  ) : null;
  return (
    <section aria-labelledby={headingId} className="media-person">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="user"
        title={data.name}
        primary={<FollowButton kind="person" value={data.name} name={data.name} />}
      />
      <div className="media-person__hero">
        <span className="media-person__portrait" aria-hidden="true">
          {data.portrait && !broken ? (
            <img src={data.portrait} alt="" onError={() => setBroken(true)} />
          ) : (
            <Icon name="user" size={56} />
          )}
        </span>
        <div className="media-person__about">
          <ul className="media-person__roles" aria-label={t("search:facet.role")}>
            {known && !data.roles.length ? <li>{known}</li> : null}
            {data.roles.map((role) => (
              <li key={role}>{t(`search:role.${role}`)}</li>
            ))}
          </ul>
          {facts.map((fact) => (
            <p key={fact} className="media-person__fact">
              {fact}
            </p>
          ))}
          <ul className="media-person__stats">
            {stats.map((stat) => (
              <li key={stat.key} data-tone={stat.tone}>
                <strong>{stat.value}</strong>
                <span>{t(`media:person.stat.${stat.key}`, { count: stat.value })}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      {profile?.biography ? (
        <section className="media-person__bio" data-open={open || undefined}>
          <h3>{t("media:person.biography")}</h3>
          <p>{profile.biography}</p>
          {profile.biography.length > 420 ? (
            <button type="button" className="media-person__more" onClick={() => setOpen(!open)}>
              {t(open ? "media:person.readLess" : "media:person.readMore")}
            </button>
          ) : null}
        </section>
      ) : null}
      {books ? null : knownFor}
      {/* issue 299: what the news sources say of them */}
      <ExternalNews
        heading={t("news:external.aboutPerson", { name: data.name })}
        asked={{ person: [data.name] }}
      />
      {data.credits.map((credit) => (
        <section key={credit.role} className="media-row media-person__section">
          <h3>
            {t(`media:person.section.${credit.role}`)}{" "}
            <span className="media-person__count">{credit.items.length}</span>
          </h3>
          <MediaGrid items={credit.items} label={t(`media:person.section.${credit.role}`)} rail />
        </section>
      ))}
      {books ? knownFor : null}
      {data.filmography?.length ? <Filmography credits={data.filmography} askable={data.askable} /> : null}
      {data.sources?.length ? (
        <p className="media-person__sources">
          {t("media:person.sources", { names: data.sources.join(", ") })}
        </p>
      ) : null}
    </section>
  );
}

/** A title's standing: available or asked for, as a badge; otherwise, when one may ask, « Ask for it » —
 * the same request as on a title's page (« not available » alone helps nobody). */
function Standing({ credit, askable }: { credit: Credit; askable: boolean }) {
  const t = useT();
  const client = useQueryClient();
  if (credit.status === "available" || credit.status === "requested") {
    return (
      <StatusBadge
        item={{ status: credit.status === "available" ? "available" : "pending", request: null }}
      />
    );
  }
  // issue 362: a book not in the library — no service asks for books
  if (credit.status === "absent") {
    return <span className="media-person__absent">{t("media:person.status.absent")}</span>;
  }
  if (!askable || credit.kind === "book") return null;
  return (
    <RequestDialog
      target={{
        tmdb_id: credit.tmdb_id,
        kind: credit.kind === "series" ? "series" : "movie",
        title: credit.title,
        ids: { tmdb: credit.tmdb_id },
      }}
      onDone={() => void client.invalidateQueries({ queryKey: ["media", "person"] })}
      trigger={
        <button type="button" className="media-person__ask">
          <Icon name="plus" size={14} />
          {t("media:person.ask")}
        </button>
      }
    />
  );
}

function posterOf(credit: Credit, size: string): string | null {
  if (credit.image_id) return imageUrl(credit.image_id);
  return credit.cover ?? metadataImage(credit.poster, size); // issue 362: a book's, through the portal
}

/** A title they are known for: the media pages' own card — poster, standing on its corner, title, role —
 * and, when it can be asked for, the button under it. */
export function KnownCard({ credit, askable }: { credit: Credit; askable: boolean }) {
  const t = useT();
  const format = useFormat();
  const src = posterOf(credit, "w342");
  const frame = (
    <>
      <span className="media-card__frame">
        <Poster src={src} kind={credit.kind} />
        <PosterBadge status={credit.status} />
        <PosterTickets mediaId={credit.object_id} />
      </span>
      <span className="media-card__title">{credit.title}</span>
    </>
  );
  return (
    <li className="media-card">
      {credit.route ? (
        <Link to={credit.route} className="media-card__link">
          {frame}
        </Link>
      ) : (
        <div className="media-card__link">{frame}</div>
      )}
      {credit.position !== null && credit.position !== undefined ? (
        <span className="media-card__note">
          {t("media:collection.volume", { number: format.number(credit.position) })}
        </span>
      ) : null}
      <span className="media-card__meta">
        {[t(`media:kind.${credit.kind}`), credit.year, credit.role].filter(Boolean).join(" · ")}
      </span>
      {credit.status === "missing" || credit.status === "unavailable" || credit.status === "absent" ? (
        <Standing credit={credit} askable={askable} />
      ) : null}
    </li>
  );
}

function Filmography({ credits, askable }: { credits: Credit[]; askable: boolean }) {
  const t = useT();
  const [filter, setFilter] = useState<Filter>("all");
  const [chosen, setChosen] = useState<string>("all");
  const dept = (value: string) => department(t, value);
  // one line per title — an actor who also produced it reads « Ethan Hunt · Production » once
  const titles = useMemo(() => {
    const merged = new Map<string, Credit & { departments: string[]; roles: string[] }>();
    for (const credit of credits) {
      const key = `${credit.kind}:${credit.tmdb_id}`;
      const known = merged.get(key);
      const role = credit.department === "cast" ? credit.role : credit.role || null;
      if (!known) {
        merged.set(key, { ...credit, departments: [credit.department], roles: role ? [role] : [] });
      } else {
        if (!known.departments.includes(credit.department)) known.departments.push(credit.department);
        if (role && !known.roles.includes(role)) known.roles.push(role);
      }
    }
    return [...merged.values()];
  }, [credits]);
  const departments = useMemo(() => [...new Set(credits.map((c) => c.department))], [credits]);
  const shown = titles.filter(
    (c) =>
      (filter === "all" ||
        (filter === "available"
          ? c.status === "available"
          : c.status === "missing" || c.status === "unavailable" || c.status === "absent")) &&
      (chosen === "all" || c.departments.includes(chosen)),
  );
  // issue 362: an author's books — a bibliography, or their works when films are there too
  const books = titles.filter((c) => c.kind === "book").length;
  const heading = t(
    books === 0
      ? "media:person.filmography"
      : books === titles.length
        ? "media:person.bibliography"
        : "media:person.works",
  );
  return (
    <section className="media-row media-person__section">
      <h3>
        {heading} <span className="media-person__count">{titles.length}</span>
      </h3>
      <div className="media-person__filters">
        <fieldset className="ds-subnav">
          <legend className="visually-hidden">{heading}</legend>
          {(["all", "available", "missing"] as Filter[]).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {t(
                value === "missing" && books === titles.length
                  ? "media:person.filter.absent"
                  : `media:person.filter.${value}`,
              )}
            </button>
          ))}
        </fieldset>
        {departments.length > 1 ? (
          <fieldset className="ds-subnav">
            <legend className="visually-hidden">{t("search:facet.role")}</legend>
            {["all", ...departments].map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={chosen === value}
                onClick={() => setChosen(value)}
              >
                {value === "all" ? t("media:person.filter.all") : dept(value)}
              </button>
            ))}
          </fieldset>
        ) : null}
      </div>
      <ul className="media-person__list">
        {shown.map((credit) => {
          const src = posterOf(credit, "w92");
          const body = (
            <>
              <span className="media-person__year">{credit.year ?? "—"}</span>
              <span className="media-person__thumb" aria-hidden="true">
                {src ? (
                  <img src={src} alt="" loading="lazy" />
                ) : (
                  <Icon name={KIND_ICONS[credit.kind] ?? "film"} size={16} />
                )}
              </span>
              <span className="media-person__line">
                <strong>{credit.title}</strong>
                <small>
                  {[
                    t(`media:kind.${credit.kind}`),
                    ...credit.roles,
                    ...credit.departments.filter((d) => d !== "cast").map(dept),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </small>
              </span>
            </>
          );
          return (
            <li key={`${credit.kind}:${credit.tmdb_id}`}>
              {credit.route ? (
                <Link to={credit.route} className="media-person__row">
                  {body}
                </Link>
              ) : (
                <div className="media-person__row">{body}</div>
              )}
              <span className="media-person__standing">
                <Standing credit={credit} askable={askable} />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default PersonPage;
