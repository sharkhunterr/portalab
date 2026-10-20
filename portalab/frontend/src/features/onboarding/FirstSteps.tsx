import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useShellPreference } from "../../shell/preferences";
import { type Mission, rewardOf, startTour, useMissions } from "./api";
import { tourForMission } from "./tours";
import "./onboarding.css";

/**
 * « First steps » (#7): the discovery missions on the dashboard — each says what it brings and opens its
 * guided tour, which shows on the real pages how to do it; done ones are ticked. Four at a time (the rest
 * one tap away), then the card goes away by itself once they are all done, or when put away
 * (``shell.onboarding.stepsHiddenAt``). Every tour stays in the guide (``/guide``).
 */
const ORDER = [
  "discover_tour",
  "discover_profile",
  "discover_dashboard",
  "discover_request",
  "discover_request_status",
  "discover_stats",
  "discover_ticket",
  "discover_shop",
  "discover_assistant", // issue 181
];
const SHOWN = 4;

export function FirstSteps() {
  const t = useT();
  const [all, setAll] = useState(false);
  const [hiddenAt, setHiddenAt, ready] = useShellPreference<string | null>(
    "shell.onboarding.stepsHiddenAt",
    null,
  );
  const missions = useMissions(ready && !hiddenAt);
  // the order a newcomer would take them, what is left first
  const rank = (m: Mission) => (m.completed_at ? 100 : 0) + (ORDER.indexOf(m.key) + 1 || 50);
  const list = [...(missions.data ?? [])].sort((a, b) => rank(a) - rank(b));
  const done = list.filter((m) => m.completed_at).length;
  if (!ready || hiddenAt || !list.length || done === list.length) return null;
  const text = (mission: Mission, field: "label" | "description") => {
    const key = `onboarding:mission.${mission.key}.${field}`;
    const translated = t(key);
    return translated === key.split(":")[1] ? (field === "label" ? mission.label : "") : translated;
  };
  const ratio = done / list.length;
  return (
    <section className="ds-card first-steps" aria-labelledby="first-steps-title">
      <header className="first-steps__head">
        <span
          className="first-steps__ring"
          style={{ "--ratio": ratio } as React.CSSProperties}
          role="img"
          aria-label={t("onboarding:steps.progress", { done, total: list.length })}
        >
          <span>
            {done}/{list.length}
          </span>
        </span>
        <div className="first-steps__intro">
          <h2 id="first-steps-title">{t("onboarding:steps.title")}</h2>
          <p>{t("onboarding:steps.lead")}</p>
        </div>
        <Link className="first-steps__guide" to="/guide">
          <Icon name="compass" size={16} />
          <span>{t("onboarding:steps.guide")}</span>
        </Link>
        <Button
          variant="ghost"
          size="icon"
          className="first-steps__hide"
          aria-label={t("onboarding:steps.hide")}
          title={t("onboarding:steps.hide")}
          onClick={() => setHiddenAt(new Date().toISOString())}
        >
          <Icon name="close" size={16} />
        </Button>
      </header>
      <ul className="first-steps__list" data-all={all || undefined}>
        {list.map((mission) => {
          const reward = rewardOf(mission);
          const complete = Boolean(mission.completed_at);
          const tour = tourForMission(mission.key);
          const body = (
            <>
              <span className="first-steps__icon" aria-hidden="true">
                <Icon name={complete ? "check" : (mission.icon ?? "target")} size={18} />
              </span>
              <span className="first-steps__text">
                <strong>{text(mission, "label")}</strong>
                <span className="first-steps__reward">
                  {complete
                    ? t("onboarding:steps.done")
                    : [
                        reward.xp ? t("onboarding:steps.xp", { amount: reward.xp }) : null,
                        reward.coins ? t("onboarding:steps.coins", { amount: reward.coins }) : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                </span>
              </span>
              {tour && !complete ? (
                <span className="first-steps__go" aria-hidden="true">
                  <Icon name="play" size={14} />
                </span>
              ) : null}
            </>
          );
          return (
            <li
              key={mission.key}
              className="first-steps__item"
              data-done={complete || undefined}
              title={text(mission, "description") || undefined}
            >
              {tour && !complete ? (
                <button
                  type="button"
                  className="first-steps__start"
                  aria-label={t("onboarding:steps.goTo", { mission: text(mission, "label") })}
                  onClick={() => startTour(tour.key)}
                >
                  {body}
                </button>
              ) : (
                <span className="first-steps__start">{body}</span>
              )}
            </li>
          );
        })}
      </ul>
      {list.length > SHOWN ? (
        <button type="button" className="first-steps__more" onClick={() => setAll(!all)}>
          {all ? t("onboarding:steps.less") : t("onboarding:steps.more", { count: list.length - SHOWN })}
        </button>
      ) : null}
    </section>
  );
}
