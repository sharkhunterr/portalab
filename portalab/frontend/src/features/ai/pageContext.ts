import { useEffect } from "react";
import { useLocation } from "react-router";

/**
 * Issue 171 — what the member is looking at, for the assistant: only what the content is and its id
 * (« media id=… », « ticket id=… ») the page declares — the assistant's tools read the rest when the
 * question needs it — or else the page's heading; sent with a new conversation so « this title », « this
 * ticket » mean what the page shows. Small on purpose: the model's context stays for the answer.
 */
let declared: { route: string; title: string } | null = null;

export function useAssistantPage(title: string | null | undefined) {
  const route = useLocation().pathname;
  useEffect(() => {
    if (!title) return;
    const mine = { route, title: title.slice(0, 200) };
    declared = mine;
    return () => {
      if (declared === mine) declared = null;
    };
  }, [route, title]);
}

export function pageContext(route: string | undefined): { route?: string; title?: string } {
  if (!route) return {};
  if (declared?.route === route) return { route, title: declared.title };
  const heading = document.querySelector("main h1, main h2")?.textContent?.replace(/\s+/g, " ").trim();
  return heading ? { route, title: heading.slice(0, 200) } : { route };
}
