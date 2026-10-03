import { useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import type { AiSource } from "../api";

/**
 * Page suggestions (spec 018 T025): buttons for the routes ``navigate.suggest`` returned — only pages of
 * the user's own navigation. No automatic navigation unless the Admin turned ``ai.autoNavigate`` on.
 */
export function NavigationSuggestion({
  sources,
  autoNavigate,
}: {
  sources: AiSource[];
  autoNavigate: boolean;
}) {
  const t = useT();
  const navigate = useNavigate();
  const pages = sources.filter((s) => s.kind === "page" && s.url?.startsWith("/"));
  const first = pages[0]?.url;
  const done = useRef(false);
  useEffect(() => {
    if (autoNavigate && first && !done.current) {
      done.current = true;
      navigate(first);
    }
  }, [autoNavigate, first, navigate]);
  if (!pages.length) return null;
  return (
    <nav aria-label={t("ai:navigation.title")} className="ds-stack--row ai-navigation">
      {pages.map((page) => (
        <Button key={page.ref} variant="secondary" onClick={() => navigate(page.url ?? "/")}>
          {t("ai:navigation.open", { page: t(page.title) })}
        </Button>
      ))}
    </nav>
  );
}
