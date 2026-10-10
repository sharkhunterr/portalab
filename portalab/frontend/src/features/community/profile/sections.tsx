import * as PopoverPrimitive from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { type ComponentType, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { useMe } from "../../auth/useAuth";
import { useAchievements } from "../../gamification/api";
import { FEED_ICONS } from "../feed/FeedText";
import { WornBadge } from "./ProfileHero";

/**
 * Profile section renderers (spec 012 T008; #46 redrawn). Built-in sections have a dedicated view; a section
 * added by a module or plugin (``register_profile_section``) renders through ``registerSectionView`` or,
 * failing that, as a plain list of its values — never as markup from the server.
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

/** About: the member's « About me », when they let this viewer see it (their name is in the hero). */
function IdentitySection({ memberId, data }: SectionViewProps) {
  const t = useT();
  const me = useMe();
  const profile = useQuery({
    queryKey: ["identity", "profile", memberId],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/users/{user_id}/profile", { params: { path: { user_id: memberId } } })).data as
        | { fields: Array<{ key: string; value: string | null }> }
        | undefined,
  });
  const bio = profile.data?.fields?.find((field) => field.key === "bio")?.value;
  if (bio) return <p className="profile-about">{bio}</p>;
  return (
    <p className="settings-muted">
      {me.data?.id === memberId
        ? t("community:about.addYours")
        : t("community:about.empty", { name: String(data.display_name ?? "") })}
    </p>
  );
}

function ProgressionSection({ data }: SectionViewProps) {
  const t = useT();
  const format = useFormat();
  const number = (key: string) => (typeof data[key] === "number" ? (data[key] as number) : 0);
  const tiles = [
    { key: "level", icon: "star", value: number("level"), label: t("community:progression.levelLabel") },
    ...("xp" in data ? [{ key: "xp", icon: "zap", value: number("xp"), label: "XP" }] : []),
    ...("contribution" in data
      ? [
          {
            key: "contribution",
            icon: "handshake",
            value: number("contribution"),
            label: t("community:progression.contributionLabel"),
          },
        ]
      : []),
    ...("achievements" in data
      ? [
          {
            key: "achievements",
            icon: "medal",
            value: number("achievements"),
            label: t("community:progression.achievementsLabel"),
          },
        ]
      : []),
  ];
  return (
    <ul className="profile-stats">
      {tiles.map((tile) => (
        <li key={tile.key} data-stat={tile.key}>
          <Icon name={tile.icon} size={18} />
          <strong>{tile.key === "xp" ? format.compact(tile.value) : format.number(tile.value)}</strong>
          <span>{tile.label}</span>
        </li>
      ))}
    </ul>
  );
}

interface AchievementItem {
  key: string;
  label: string;
  description?: string;
  icon?: string;
  rarity?: string;
  unlocked_at: string;
}

/** One unlocked achievement as a medal; its name, description, rarity and date on hover, focus or tap. */
function AchievementBadge({ item }: { item: AchievementItem }) {
  const t = useT();
  const format = useFormat();
  const [open, setOpen] = useState(false);
  const rarity = item.rarity ?? "common";
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          className="profile-medal"
          data-rarity={rarity}
          aria-label={item.label}
          onPointerEnter={(event) => {
            if (event.pointerType === "mouse") setOpen(true);
          }}
          onPointerLeave={(event) => {
            if (event.pointerType === "mouse") setOpen(false);
          }}
        >
          <Icon name={item.icon ?? "trophy"} size={22} />
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          className="ds-popover profile-medal__card"
          data-rarity={rarity}
          side="top"
          sideOffset={8}
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <strong>{item.label}</strong>
          {item.description ? <p>{item.description}</p> : null}
          <span className="profile-medal__meta">
            <span className="profile-medal__rarity">{t(`gamification:achievements.rarity.${rarity}`)}</span>
            <time dateTime={item.unlocked_at}>{format.date(item.unlocked_at)}</time>
          </span>
          <PopoverPrimitive.Arrow className="profile-medal__arrow" />
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

const RARITIES = ["legendary", "epic", "rare", "common"] as const;

/** Unlocked achievements (#51): the rarest first, a legend counting each rarity, a medal per rarity. */
function AchievementsSection({ data }: SectionViewProps) {
  const t = useT();
  const items = (Array.isArray(data.items) ? data.items : []) as AchievementItem[];
  const rank = (item: AchievementItem) => {
    const at = RARITIES.indexOf((item.rarity ?? "common") as (typeof RARITIES)[number]);
    return at < 0 ? RARITIES.length : at;
  };
  const sorted = [...items].sort((a, b) => rank(a) - rank(b) || b.unlocked_at.localeCompare(a.unlocked_at));
  const counts = RARITIES.map((rarity) => ({
    rarity,
    count: items.filter((item) => (item.rarity ?? "common") === rarity).length,
  })).filter((entry) => entry.count);
  return (
    <>
      <ul className="profile-rarities" aria-label={t("community:achievements.byRarity")}>
        {counts.map((entry) => (
          <li key={entry.rarity} data-rarity={entry.rarity}>
            <span className="profile-rarities__gem" aria-hidden="true" />
            {t(`gamification:achievements.rarity.${entry.rarity}`)}
            <strong>{entry.count}</strong>
          </li>
        ))}
      </ul>
      <ul className="profile-medals">
        {sorted.map((item) => (
          <li key={item.key}>
            <AchievementBadge item={item} />
          </li>
        ))}
      </ul>
    </>
  );
}

interface ActivityItem {
  id: string;
  kind: string;
  params: Record<string, unknown>;
  occurred_at: string;
}

const KNOWN = new Set(["achievement.unlocked", "user.level_up", "quest.completed", "project.created"]);

/** Recent activity (#46): a badge per kind, a title, what it was about, and when. */
function ActivitySection({ data }: SectionViewProps) {
  const format = useFormat();
  const t = useT();
  const achievements = useAchievements();
  const items = (Array.isArray(data.items) ? data.items : []) as ActivityItem[];
  const detail = (item: ActivityItem): string | null => {
    const params = item.params;
    if (item.kind === "achievement.unlocked" && typeof params.achievement === "string") {
      const known = Array.isArray(achievements.data) ? achievements.data : [];
      const found = known.find((a) => a.key === params.achievement);
      return found ? (found.label ?? t("community:feed.hiddenAchievement")) : null;
    }
    if (item.kind === "quest.completed" && typeof params.kind === "string")
      return t(`community:activity.questKind.${params.kind}`);
    if (item.kind === "project.created" && typeof params.title === "string") return params.title;
    return null;
  };
  return (
    <>
      <ul className="profile-activity">
        {items.map((item) => {
          const kind = KNOWN.has(item.kind) ? item.kind : "generic";
          const sub = detail(item);
          const level = typeof item.params.level === "number" ? item.params.level : "";
          return (
            <li key={item.id} data-kind={kind}>
              <span className="profile-activity__badge" aria-hidden="true">
                <Icon name={FEED_ICONS[item.kind] ?? "activity"} size={16} />
              </span>
              <span className="profile-activity__text">
                <strong>{t(`community:activity.${kind}`, { level })}</strong>
                {sub ? <span>{sub}</span> : null}
              </span>
              <time
                dateTime={item.occurred_at}
                className="profile-activity__when"
                title={format.dateTime(item.occurred_at)}
              >
                {format.relative((new Date(item.occurred_at).getTime() - Date.now()) / 1000)}
              </time>
            </li>
          );
        })}
      </ul>
      <Link to="/community/feed" className="profile-activity__more">
        {t("community:nav.feed")}
        <Icon name="chevron-right" size={14} />
      </Link>
    </>
  );
}

interface OwnedLook {
  key: string;
  names?: Record<string, string>;
  icon?: string | null;
  style?: string | null;
}

/** Badges and titles the member owns (#46): drawn as they are worn, in the viewer's language. */
function CosmeticsSection({ data }: SectionViewProps) {
  const { language } = useLocaleContext();
  const nameOf = (item: OwnedLook) =>
    item.names?.[language] ?? item.names?.[language.split("-")[0] ?? ""] ?? item.names?.en ?? item.key;
  const list = (key: string) =>
    (Array.isArray(data[key]) ? (data[key] as unknown[]) : []).filter(
      (item): item is OwnedLook => typeof item === "object" && item !== null,
    );
  const titles = list("titles");
  const badges = list("badges");
  return (
    <div className="profile-looks">
      {titles.length ? (
        <ul>
          {titles.map((item) => (
            <li key={item.key}>
              <WornBadge
                kind="title"
                item={{ key: item.key, label: nameOf(item), style: item.style ?? null }}
              />
            </li>
          ))}
        </ul>
      ) : null}
      {badges.length ? (
        <ul>
          {badges.map((item) => (
            <li key={item.key}>
              <WornBadge
                kind="badge"
                item={{
                  key: item.key,
                  label: nameOf(item),
                  icon: item.icon ?? null,
                  style: item.style ?? null,
                }}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

registerSectionView("cosmetics", CosmeticsSection);
registerSectionView("identity", IdentitySection);
registerSectionView("progression", ProgressionSection);
registerSectionView("achievements", AchievementsSection);
registerSectionView("activity", ActivitySection);
