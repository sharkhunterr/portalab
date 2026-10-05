import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { posterOf, type SoonCard } from "./api";
import "./requests.css";

/**
 * Coming soon (027): requests being downloaded or imported — with their progress and expected time — or with
 * a release date. Shared by the « My requests » page and the dashboard widget (no chart library here).
 */
export function Poster({
  card,
  size = "md",
}: {
  card: { image_id: string | null; poster_ref?: string | null };
  size?: "sm" | "md";
}) {
  const src = posterOf(card);
  return (
    <span className="requests-poster" data-size={size}>
      {src ? <img src={src} alt="" loading="lazy" /> : <Icon name="film" size={size === "sm" ? 18 : 26} />}
    </span>
  );
}

export function SoonList({ items, compact = false }: { items: SoonCard[]; compact?: boolean }) {
  const t = useT();
  const format = useFormat();
  return (
    <ul className="requests-soon" data-compact={compact || undefined}>
      {items.map((card) => {
        const episode =
          card.episode?.season != null && card.episode?.episode != null
            ? `S${String(card.episode.season).padStart(2, "0")}E${String(card.episode.episode).padStart(2, "0")}`
            : null;
        const body = (
          <>
            <Poster card={card} size={compact ? "sm" : "md"} />
            <span className="requests-soon__main">
              <strong>{card.title}</strong>
              <span className="requests-soon__phase" data-phase={card.phase}>
                <Icon
                  name={
                    card.phase === "release"
                      ? "calendar"
                      : card.phase === "importing"
                        ? "inbox"
                        : "arrow-down"
                  }
                  size={14}
                />
                {t(`media:myRequests.phase.${card.phase}`)}
                {episode ? ` · ${episode}` : ""}
                {card.count && card.count > 1
                  ? ` · ${t("media:myRequests.files", { count: card.count })}`
                  : ""}
              </span>
              {card.phase === "release" && card.release_at ? (
                <span className="admin-muted">
                  {t(`media:widget.release.${card.release_type ?? "release"}`)} ·{" "}
                  {format.date(card.release_at, "long")}
                </span>
              ) : (
                <>
                  <span
                    className="requests-meter"
                    role="progressbar"
                    aria-label={card.title}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round((card.progress ?? 0) * 100)}
                  >
                    <span style={{ inlineSize: `${Math.round((card.progress ?? 0) * 100)}%` }} />
                  </span>
                  <span className="admin-muted">
                    {format.percent(card.progress ?? 0)}
                    {card.eta
                      ? ` · ${t("media:myRequests.eta", { when: format.relative((Date.parse(card.eta) - Date.now()) / 1000) })}`
                      : ""}
                  </span>
                </>
              )}
            </span>
          </>
        );
        return (
          <li key={card.request_id}>
            {card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}
          </li>
        );
      })}
    </ul>
  );
}
