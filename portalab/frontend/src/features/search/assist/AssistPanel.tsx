import { useId } from "react";
import { useLocation } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useSlots } from "../../../shell/slots/providers";
import type { ItemOut } from "../api";
import { useSearchAssist } from "./useSearchAssist";

/**
 * Assistant analysis (spec 008 T020; FR-004/005/023): visually distinct from the results, labelled as an
 * interpretation, with its sources listed separately; its own unavailable/error states and retry never
 * affect the classic results.
 */
export function AssistPanel({ query, items }: { query: string; items: ItemOut[] }) {
  const t = useT();
  const headingId = useId();
  const assist = useSearchAssist();
  const { ai } = useSlots(); // issue 171: the analysis goes on as a conversation
  const location = useLocation();
  const titles = new Map(items.map((item) => [`${item.kind}:${item.id}`, item]));
  const ask = () =>
    assist.ask(
      query,
      items.map((item) => ({ kind: item.kind, id: item.id })),
    );
  return (
    <aside aria-labelledby={headingId} className="search-assist" data-state={assist.state}>
      <h3 id={headingId}>{t("search:assist.title")}</h3>
      {assist.state === "idle" ? (
        <Button variant="secondary" onClick={ask} disabled={!query.trim()}>
          {t("search:assist.ask")}
        </Button>
      ) : null}
      {ai?.available && query.trim() ? (
        <Button variant="ghost" onClick={() => ai.open({ route: location.pathname, question: query.trim() })}>
          {t("search:assist.converse")}
        </Button>
      ) : null}
      {assist.state === "streaming" ? <FunctionalState state="loading" /> : null}
      {assist.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("search:assist.unavailable")} />
      ) : null}
      {assist.state === "error" ? (
        <FunctionalState
          state="error"
          label={t("search:assist.error")}
          onRetry={ask}
          retryLabel={t("search:assist.retry")}
        />
      ) : null}
      {assist.synthesis.length ? (
        <div className="search-assist__synthesis">
          <p className="search-assist__note">{t("search:assist.note")}</p>
          {assist.synthesis.map((text, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: streamed paragraphs keep their order
            <p key={index}>{text}</p>
          ))}
        </div>
      ) : null}
      {assist.sources.length ? (
        <>
          <h4>{t("search:assist.sources")}</h4>
          <ul className="search-assist__sources">
            {assist.sources.map((source) => {
              const item = titles.get(`${source.kind}:${source.id}`);
              return (
                <li key={`${source.kind}:${source.id}`}>
                  {item ? item.title : `${source.kind} ${source.id}`}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
    </aside>
  );
}
