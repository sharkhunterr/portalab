import type { components } from "../../../api/generated/schema";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { AgeBadge } from "../AgeBadge";

type AgeRating = components["schemas"]["AgeRating"];
type Release = components["schemas"]["AgeRatingRelease"];

/** The order releases are told in: as one watches at home first (the household's rule), then the cinema. */
const ORDER = ["tv", "digital", "physical", "cinema", "cinema_limited", "premiere"];

function regionName(locale: string, code: string): string {
  try {
    return new Intl.DisplayNames([locale], { type: "region" }).of(code) ?? code;
  } catch {
    return code; // an unknown code: the code itself
  }
}

/**
 * Issue 478 — a title's classification in full: the age a household profile is held to and what it follows
 * (the TV's rating first, then the platforms', then the cinema's), the CNC's decision for a film (« tous
 * publics avec avertissement »), and every release's rating, country by country — the cinema, the TV, each
 * platform, with its note (« Netflix », « Visa CNC 142250 ») and its descriptors: the portal's country
 * shown, the others folded under « N other countries ».
 */
export function RatingsBlock({
  rating,
  inGrid = false,
}: {
  rating: AgeRating | null | undefined;
  /** among the details' blocks (a film's: after its production), else a section of its own */
  inGrid?: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const releases = rating?.releases ?? [];
  const cnc = rating?.cnc;
  if (!rating || (!releases.length && !cnc)) return null;
  const own = rating.country ?? null;
  // the portal's country (its administrator's choice) shown, every other one folded away
  const mine = releases.filter((r) => r.country === own);
  const others = [...new Set(releases.map((r) => r.country))]
    .filter((country) => country !== own)
    .sort((a, b) => regionName(locale, a).localeCompare(regionName(locale, b), locale));
  const list = (items: Release[]) => (
    <dl className="media-enriched__pairs">
      {[...items]
        .sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type))
        .map((release, index) => (
          <div key={`${release.type}-${release.certification}-${release.note ?? index}`}>
            <dt>{t(`media:ratings.type.${release.type}`)}</dt>
            <dd>
              <span className="media-ratings__value">{release.certification}</span>
              {release.note || release.date ? (
                <span className="media-ratings__note">
                  {[
                    release.note,
                    release.date ? format.date(`${release.date.slice(0, 10)}T12:00:00Z`, "medium") : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              ) : null}
              {release.descriptors?.length ? (
                <span className="media-ratings__note">{release.descriptors.join(", ")}</span>
              ) : null}
            </dd>
          </div>
        ))}
    </dl>
  );
  const block = (
    <div className="media-enriched__block media-ratings">
      <h3>{t("media:ratings.title")}</h3>
      <dl className="media-enriched__pairs">
        {rating.age !== null && rating.age !== undefined ? (
          <div>
            <dt>{t("media:ratings.held")}</dt>
            <dd className="media-ratings__held">
              <AgeBadge age={rating.age} />
              {rating.basis ? (
                <span className="media-ratings__note">
                  {t(`media:ratings.basis.${rating.basis}`, {
                    country: rating.basis_country ? regionName(locale, rating.basis_country) : "",
                  })}
                </span>
              ) : null}
            </dd>
          </div>
        ) : null}
        {cnc ? (
          <div>
            <dt>{t("media:ratings.cnc")}</dt>
            <dd className="media-ratings__cnc" data-warning={cnc.warning || undefined}>
              {cnc.warning ? <Icon name="warning" size={14} /> : null}
              <span>{cnc.warning ? t("media:ratings.cncWarning") : cnc.decision}</span>
              <span className="media-ratings__note">{t("media:ratings.visa", { visa: cnc.visa })}</span>
            </dd>
          </div>
        ) : null}
        {rating.warnings?.length ? (
          <div>
            <dt>{t("media:ratings.warnings")}</dt>
            <dd className="media-ratings__warnings">
              {rating.warnings.map((kind) => (
                <span key={kind} className="media-ratings__warning">
                  <Icon name="warning" size={14} />
                  {t(`media:ratings.warning.${kind}`)}
                </span>
              ))}
            </dd>
          </div>
        ) : null}
      </dl>
      {mine.length ? (
        <div className="media-ratings__country">
          <h4>{regionName(locale, own as string)}</h4>
          {list(mine)}
        </div>
      ) : null}
      {others.length ? (
        <details className="media-ratings__others">
          <summary>{t("media:ratings.others", { count: others.length })}</summary>
          {others.map((country) => (
            <div key={country} className="media-ratings__country">
              <h4>{regionName(locale, country)}</h4>
              {list(releases.filter((r) => r.country === country))}
            </div>
          ))}
        </details>
      ) : null}
    </div>
  );
  if (inGrid) return block;
  return (
    <section className="media-enriched" aria-label={t("media:ratings.title")}>
      <div className="media-enriched__grid">{block}</div>
    </section>
  );
}
