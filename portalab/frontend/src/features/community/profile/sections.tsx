import type { ComponentType } from "react";
import { Link } from "react-router";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { FeedText } from "../feed/FeedText";

/**
 * Profile section renderers (spec 012 T008). Built-in sections have a dedicated view; a section added by a
 * module or plugin (``register_profile_section``) renders through ``registerSectionView`` or, failing that,
 * as a plain list of its values — never as markup from the server.
 */
export interface SectionViewProps {
  memberId: string;
  data: Record<string, unknown>;
}

const views = new Map<string, ComponentType<SectionViewProps>>();

export function registerSectionView(key: string, view: ComponentType<SectionViewProps>): void {
  views.set(key, view);
}

export function sectionView(key: string): ComponentType<SectionViewProps> {
  return views.get(key) ?? GenericSection;
}

function GenericSection({ data }: SectionViewProps) {
  const entries = Object.entries(data).filter(([, v]) => typeof v === "string" || typeof v === "number");
  return (
    <dl className="community-values">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function IdentitySection({ data }: SectionViewProps) {
  return <p className="community-name">{String(data.display_name ?? "")}</p>;
}

function ProgressionSection({ data }: SectionViewProps) {
  const t = useT();
  const number = (key: string) => (typeof data[key] === "number" ? (data[key] as number) : 0);
  return (
    <ul className="community-values">
      <li>{t("community:progression.level", { level: number("level") })}</li>
      {"xp" in data ? <li>{t("community:progression.xp", { xp: number("xp") })}</li> : null}
      {"contribution" in data ? (
        <li>{t("community:progression.contribution", { contribution: number("contribution") })}</li>
      ) : null}
      {"achievements" in data ? (
        <li>{t("community:progression.achievements", { count: number("achievements") })}</li>
      ) : null}
    </ul>
  );
}

interface AchievementItem {
  key: string;
  label: string;
  unlocked_at: string;
}

function AchievementsSection({ data }: SectionViewProps) {
  const format = useFormat();
  const items = (Array.isArray(data.items) ? data.items : []) as AchievementItem[];
  return (
    <ul className="community-badges">
      {items.map((item) => (
        <li key={item.key}>
          <strong>{item.label}</strong>{" "}
          <time dateTime={item.unlocked_at} className="community-meta">
            {format.date(item.unlocked_at)}
          </time>
        </li>
      ))}
    </ul>
  );
}

interface ActivityItem {
  id: string;
  kind: string;
  params: Record<string, unknown>;
  occurred_at: string;
}

function ActivitySection({ memberId, data }: SectionViewProps) {
  const format = useFormat();
  const t = useT();
  const items = (Array.isArray(data.items) ? data.items : []) as ActivityItem[];
  return (
    <>
      <ul className="community-feed">
        {items.map((item) => (
          <li key={item.id}>
            <FeedText kind={item.kind} actorId={memberId} actorName={null} params={item.params} />{" "}
            <time dateTime={item.occurred_at} className="community-meta">
              {format.dateTime(item.occurred_at)}
            </time>
          </li>
        ))}
      </ul>
      <Link to="/community/feed">{t("community:nav.feed")}</Link>
    </>
  );
}

registerSectionView("identity", IdentitySection);
registerSectionView("progression", ProgressionSection);
registerSectionView("achievements", AchievementsSection);
registerSectionView("activity", ActivitySection);
