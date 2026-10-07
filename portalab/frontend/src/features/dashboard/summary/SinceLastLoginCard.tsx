import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "../widgets/registry";

// each kind of news keeps its icon and colour (theme tokens)
const KINDS: Record<string, { icon: string; tone: string }> = {
  media_request: { icon: "inbox", tone: "var(--rarity-rare)" },
  media: { icon: "film", tone: "var(--cal-movie)" },
  news: { icon: "newspaper", tone: "var(--cal-news)" },
  support: { icon: "lifebuoy", tone: "var(--cal-series)" },
  feedback: { icon: "message", tone: "var(--cal-series)" },
  progression: { icon: "trophy", tone: "var(--rarity-legendary)" },
  shop: { icon: "shop", tone: "var(--cal-book)" },
  services: { icon: "server", tone: "var(--cal-incident)" },
};

interface SummaryItem {
  kind: string;
  occurred_at: string;
  ref: string;
  title?: string | null;
  title_key?: string | null;
  title_args?: Record<string, unknown>;
  detail?: string | null;
}

/**
 * "Since your last visit" (spec 009 T028; 027: a widget like the others, placed and hidden at will): what
 * changed for me — my requests now available, answers on my tickets, new titles, news, my progress, the
 * shop, services in trouble — one line each with its icon and a detail line, most important first;
 * « mark all as seen » moves the boundary.
 */
function SinceLastVisitWidget({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const data = (payload.data ?? {}) as { items?: SummaryItem[]; unavailable?: string[] };
  const items = Array.isArray(data.items) ? data.items : [];
  async function seen() {
    await api.POST("/api/v1/dashboard/since-last-login/seen", { body: {} });
    await client.invalidateQueries({ queryKey: ["widget", "dashboard.since_last_visit"] });
    await client.invalidateQueries({ queryKey: ["dashboard", "summary"] });
  }
  return (
    <div className="dashboard-summary">
      {items.length ? (
        <ul className="dashboard-summary__list">
          {items.map((item) => {
            const kind = KINDS[item.kind] ?? { icon: "sparkles", tone: "var(--color-accent)" };
            const title =
              item.title ??
              (item.title_key ? t(item.title_key, item.title_args as Record<string, string>) : item.ref);
            return (
              <li key={`${item.kind}:${item.ref}:${item.occurred_at}`}>
                <Link
                  className="dashboard-summary__item"
                  to={item.ref.startsWith("/") ? item.ref : "/"}
                  style={{ "--kind": kind.tone } as React.CSSProperties}
                >
                  <span className="dashboard-summary__kind" aria-hidden="true">
                    <Icon name={kind.icon} size={18} />
                  </span>
                  <span className="dashboard-summary__text">
                    <strong>{title}</strong>
                    {item.detail ? <span className="dashboard-summary__detail">{item.detail}</span> : null}
                  </span>
                  <span className="dashboard-summary__when">
                    {format.relative((Date.parse(item.occurred_at) - Date.now()) / 1000)}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="widget__meta">{t("dashboard:summary.nothing")}</p>
      )}
      {data.unavailable?.length ? <p className="widget__meta">{t("dashboard:summary.unavailable")}</p> : null}
      {items.length ? (
        <Button variant="ghost" onClick={seen}>
          <Icon name="check" size={16} />
          {t("dashboard:summary.allSeen")}
        </Button>
      ) : null}
    </div>
  );
}

registerWidgetComponent("dashboard.since_last_visit", SinceLastVisitWidget);
