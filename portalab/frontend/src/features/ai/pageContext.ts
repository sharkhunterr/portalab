import { useEffect } from "react";
import { useLocation } from "react-router";

/**
 * Issue 171 — what the member is looking at, for the assistant: what the content is, its id and its name
 * (« media id=… « Heat » (movie) ») the page declares — the name lets the model tell whether a question is
 * about the page; the assistant's tools read the rest when the
 * question needs it — or else the page's heading; sent with a new conversation so « this title », « this
 * ticket » mean what the page shows. Small on purpose: the model's context stays for the answer.
 */
let declared: { route: string; title: string; label: string } | null = null;

/** ``title``: what the model reads (« media id=… »); ``label``: what the member reads at the top of the
 * assistant (« Avatar : Les Sept Refuges · series ») — never sent. */
export function useAssistantPage(title: string | null | undefined, label?: string | null) {
  const route = useLocation().pathname;
  useEffect(() => {
    if (!title) return;
    const mine = { route, title: title.slice(0, 200), label: (label || title).slice(0, 200) };
    declared = mine;
    return () => {
      if (declared === mine) declared = null;
    };
  }, [route, title, label]);
}

function heading(): string | undefined {
  return document.querySelector("main h1, main h2")?.textContent?.replace(/\s+/g, " ").trim() || undefined;
}

/** What the top of the assistant says the member is looking at. */
export function pageLabel(route: string | undefined): string | undefined {
  if (!route) return undefined;
  return declared?.route === route ? declared.label : heading();
}

export function pageContext(route: string | undefined): { route?: string; title?: string } {
  if (!route) return {};
  if (declared?.route === route) return { route, title: declared.title };
  const text = heading();
  return text ? { route, title: text.slice(0, 200) } : { route };
}
