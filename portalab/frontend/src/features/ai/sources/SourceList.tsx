import { Link } from "react-router";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { AiCaveat, AiSource } from "../api";

/**
 * Sources of one answer (spec 018 T021, FR-012..014): numbered like the ``[n]`` markers in the text, each
 * with a **text** class label (live data / history / knowledge base) and ``as of`` date; degraded tool
 * results become a caveat note; an answer citing nothing is labelled as the assistant's interpretation.
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
          <ol className="ai-source-list">
            {sources.map((source) => (
              <li key={source.n} value={source.n} data-class={source.class}>
                <span className="ds-badge">{t(`ai:sources.class.${source.class}`)}</span>{" "}
                {source.url?.startsWith("/") ? (
                  <Link to={source.url}>{source.title}</Link>
                ) : (
                  <span>{source.title}</span>
                )}
                {source.as_of ? (
                  <span className="ai-meta">
                    {" "}
                    · {t("ai:sources.asOf", { date: format.dateTime(source.as_of) })}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}
