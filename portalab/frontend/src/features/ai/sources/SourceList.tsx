import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { AiCaveat, AiSource } from "../api";

// issue 171: what each kind of source looks like when it has no picture of its own
const KIND_ICONS: Record<string, string> = {
  media: "film",
  ticket: "lifebuoy",
  ticket_draft: "ticket",
  wiki: "book-open",
  news: "newspaper",
  service: "server",
  marketplace: "shop",
  progression: "activity",
  page: "compass",
};

/**
 * Sources of one answer (spec 018 T021, FR-012..014): numbered like the ``[n]`` markers in the text, each
 * with a **text** class label (live data / history / knowledge base) and ``as of`` date; degraded tool
 * results become a caveat note; an answer citing nothing is labelled as the assistant's interpretation.
 * Issue 171: each source is a card — a title's poster, else the icon of its kind — opening its page.
 */
export function SourceList({
  sources,
  caveats,
  interpretation,
}: {
  sources: AiSource[];
  caveats: AiCaveat[];
  interpretation: boolean;
}) {
  const t = useT();
  const format = useFormat();
  return (
    <div className="ai-sources">
      {caveats.length ? (
        <div role="note" className="ai-caveats">
          {caveats.map((caveat) => (
            <p key={`${caveat.tool}-${caveat.state}`}>
              {t(`ai:sources.caveat.${caveat.state}`, { tool: caveat.tool })}
            </p>
          ))}
        </div>
      ) : null}
      {interpretation ? <p className="ai-interpretation">{t("ai:sources.interpretation")}</p> : null}
      {sources.length ? (
        <section aria-label={t("ai:sources.title")}>
          <h4>{t("ai:sources.title")}</h4>
          <ol className="ai-cards">
            {sources.map((source) => {
              const body = (
                <>
                  {source.image?.startsWith("/api/") ? (
                    <img className="ai-card__poster" src={source.image} alt="" loading="lazy" />
                  ) : (
                    <span className="ai-card__icon" aria-hidden="true">
                      <Icon name={KIND_ICONS[source.kind] ?? "compass"} size={18} />
                    </span>
                  )}
                  <span className="ai-card__text">
                    <span className="ai-card__title">
                      <span className="ai-card__n" aria-hidden="true">
                        {source.n}
                      </span>
                      {source.title}
                    </span>
                    <span className="ai-card__detail">
                      {source.detail ?? t(`ai:sources.class.${source.class}`)}
                      {source.as_of && !source.detail
                        ? ` · ${t("ai:sources.asOf", { date: format.dateTime(source.as_of) })}`
                        : ""}
                    </span>
                  </span>
                </>
              );
              return (
                <li key={source.n} value={source.n} data-class={source.class} data-kind={source.kind}>
                  {source.url?.startsWith("/") ? (
                    <Link className="ai-card" to={source.url}>
                      {body}
                    </Link>
                  ) : (
                    <span className="ai-card">{body}</span>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}
    </div>
  );
}
