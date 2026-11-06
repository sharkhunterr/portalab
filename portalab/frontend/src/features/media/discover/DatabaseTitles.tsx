import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { useT } from "../../../i18n/hooks/useT";
import { Poster } from "../MediaGrid";

/**
 * Issue 375: « Ask for a title » finds books and games too — those the library lacks, from the book and game
 * databases (Hardcover, IGDB), told in the member's language; each opens its sheet, where it is asked of the
 * team.
 */
export interface DatabaseTitle {
  kind: string;
  title: string;
  year: number | null;
  creator: string | null;
  cover: string | null;
  route: string;
}

export function useDatabaseTitles(q: string) {
  return useQuery({
    queryKey: ["media", "discover", "titles", q],
    enabled: q.trim().length > 1,
    retry: false,
    staleTime: 10 * 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/media/discover/titles", { params: { query: { q } } }))
        .data as unknown as DatabaseTitle[],
  });
}

export function DatabaseTitleCard({ item }: { item: DatabaseTitle }) {
  const t = useT();
  return (
    <li className="media-card discover-card">
      <Link to={item.route} className="media-card__link">
        <span className="media-card__frame">
          <Poster src={item.cover} kind={item.kind} />
        </span>
        <span className="media-card__title">{item.title}</span>
      </Link>
      <span className="media-card__meta">
        {[t(`media:kind.${item.kind}`), item.year, item.creator].filter(Boolean).join(" · ")}
      </span>
    </li>
  );
}
