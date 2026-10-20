import { useId } from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { useT } from "../../i18n/hooks/useT";
import { useNavigationView } from "../../shell/nav/NavigationProvider";
import { useShellPreference } from "../../shell/preferences";
import { useAiStatus } from "../ai/api";
import { openWelcome, rewardOf, startTour, useMissions } from "./api";
import { TOURS, type TourDef, type TourGroup } from "./tours";
import "./onboarding.css";

/**
 * The guide (#7): every guided tour of the portal on one page, by theme — what it shows, how long it
 * takes, whether it was seen, and what its first-steps mission still brings. Only the tours of pages the
 * member can open are offered. The welcome screens can be seen again from here too.
 */
const GROUPS: readonly TourGroup[] = ["start", "media", "play", "help"];

function useReachable(): (tour: TourDef) => boolean {
  const { view } = useNavigationView();
  const routes = [...view.groups.flatMap((g) => g.entries), ...view.personal]
    .map((entry) => entry.route)
    .filter((route): route is string => Boolean(route));
  return (tour) =>
    tour.route === "/" ||
    view.degraded ||
    routes.length === 0 ||
    routes.some((route) => route !== "/" && (tour.route === route || tour.route.startsWith(`${route}/`)));
}

export default function GuidePage() {
  const t = useT();
  const headingId = useId();
  const reachable = useReachable();
  const [seen] = useShellPreference<string[]>("shell.onboarding.toursSeen", []);
  const missions = useMissions();
  const missionOf = (tour: TourDef) => missions.data?.find((m) => m.key === tour.mission);
  const assistant = useAiStatus().data?.available === true; // issue 181: its tours while it is on
  const tours = TOURS.filter((tour) => reachable(tour) && (tour.requires !== "assistant" || assistant));
  const portal = tours.find((tour) => tour.key === "portal");
  return (
    <section aria-labelledby={headingId} className="guide-page">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="compass"
        title={t("onboarding:guide.title")}
        context={t("onboarding:guide.lead", {
          seen: tours.filter((tour) => seen.includes(tour.key)).length,
          total: tours.length,
        })}
        secondary={
          <Button variant="secondary" onClick={openWelcome}>
            <Icon name="sparkles" size={18} />
            {t("onboarding:guide.welcome")}
          </Button>
        }
      />
      {portal ? (
        <div className="guide-hero">
          <span className="guide-hero__art" aria-hidden="true">
            <Icon name="compass" size={34} />
          </span>
          <div className="guide-hero__text">
            <h3>{t("onboarding:guide.heroTitle")}</h3>
            <p>{t("onboarding:guide.heroText")}</p>
          </div>
          <Button onClick={() => startTour("portal")}>
            <Icon name="play" size={18} />
            {seen.includes("portal") ? t("onboarding:guide.again") : t("onboarding:guide.start")}
          </Button>
        </div>
      ) : null}
      {GROUPS.map((group) => {
        const list = tours.filter((tour) => tour.group === group && tour.key !== "portal");
        if (!list.length) return null;
        return (
          <section key={group} className="guide-group" aria-labelledby={`guide-${group}`}>
            <h3 id={`guide-${group}`}>{t(`onboarding:guide.group.${group}`)}</h3>
            <ul className="guide-list">
              {list.map((tour) => {
                const mission = missionOf(tour);
                const reward = mission && !mission.completed_at ? rewardOf(mission) : null;
                const viewed = seen.includes(tour.key);
                return (
                  <li key={tour.key} className="guide-card" data-seen={viewed || undefined}>
                    <span className="guide-card__icon" aria-hidden="true">
                      <Icon name={tour.icon} size={22} />
                    </span>
                    <div className="guide-card__text">
                      <h4>{t(`onboarding:tours.${tour.key}.title`)}</h4>
                      <p>{t(`onboarding:tours.${tour.key}.description`)}</p>
                      <p className="guide-card__meta">
                        <span>{t("onboarding:guide.steps", { count: tour.steps.length })}</span>
                        {viewed ? (
                          <span className="guide-card__seen">
                            <Icon name="check" size={14} />
                            {t("onboarding:guide.seen")}
                          </span>
                        ) : null}
                        {reward && (reward.xp || reward.coins) ? (
                          <span className="guide-card__reward">
                            {[
                              reward.xp ? t("onboarding:steps.xp", { amount: reward.xp }) : null,
                              reward.coins ? t("onboarding:steps.coins", { amount: reward.coins }) : null,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        ) : null}
                      </p>
                    </div>
                    <Button
                      variant={viewed ? "ghost" : "secondary"}
                      onClick={() => startTour(tour.key)}
                      aria-label={`${viewed ? t("onboarding:guide.again") : t("onboarding:guide.start")} : ${t(`onboarding:tours.${tour.key}.title`)}`}
                    >
                      <Icon name="play" size={16} />
                      {viewed ? t("onboarding:guide.again") : t("onboarding:guide.start")}
                    </Button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </section>
  );
}
