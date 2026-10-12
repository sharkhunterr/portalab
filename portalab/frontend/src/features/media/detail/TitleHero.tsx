import type { ReactNode } from "react";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { Poster } from "../MediaGrid";
import "../discover/discover.css";

/**
 * A title's head, the same everywhere (#4: a library title and one to ask for): its backdrop behind, the
 * poster in front, the title with its facts (year, kind, runtime, rating), its badges (available, asked
 * for, in progress, watched) and its actions (watch, the service's page, ask for it, the trailer).
 */
export function TitleHero({
  headingId,
  level = 1,
  title,
  kind,
  facts,
  poster,
  backdrop,
  badges,
  primary,
  secondary,
  children,
}: {
  headingId: string;
  level?: 1 | 2;
  title: ReactNode;
  kind: string;
  facts: Array<string | null | undefined | false>;
  poster: string | null;
  backdrop: string | null;
  badges?: ReactNode;
  primary?: ReactNode;
  secondary?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="discover-title__hero">
      {backdrop ? <img className="discover-title__backdrop" src={backdrop} alt="" /> : null}
      <div className="discover-title__head">
        <span className="discover-title__poster">
          <Poster src={poster} kind={kind} />
        </span>
        <div className="discover-title__text">
          <PageHeader
            level={level}
            titleId={headingId}
            title={title}
            context={facts.filter(Boolean).join(" · ")}
            primary={primary}
            secondary={secondary}
          />
          {badges ? <div className="discover-title__state">{badges}</div> : null}
          {children}
        </div>
      </div>
    </header>
  );
}
