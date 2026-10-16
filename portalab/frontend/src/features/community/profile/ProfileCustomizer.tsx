import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { AdminEmpty, AdminTabs } from "../../../design-system/admin/AdminKit";
import { LevelBadge } from "../../../design-system/components/Badges";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useNotify } from "../../../design-system/components/Notification";
import { Dialog } from "../../../design-system/components/Overlays";
import { fxFrameOf } from "../../../design-system/themes/premium/fxLooks";
import { gpuLook } from "../../../design-system/visuals/gpu";
import { useT } from "../../../i18n/hooks/useT";
import { InShop } from "../../appearance/InShop";
import { HdTag, isHdAmbient, isHdLevelBadge, RarityTag } from "../../appearance/Rarity";
import { WaitingTag } from "../../appearance/waiting";
import { useProgression } from "../../gamification/api";
import { imageUrl } from "../../media/api";
import { backdropUrl, type LookChoice, useEquipLook, useProfileLooks, type WornItem } from "./looks";
import { BannerArt, FramedAvatar, StyledName, WornBadge } from "./ProfileHero";

/**
 * Profile customisation (027), Steam-like: the banner (free designs, those bought in the shop or in a
 * theme pack), the avatar frame, the backdrop of a film or a series as the banner (unlocked once in the
 * shop), the name's font and effect, a title and a showcase of three badges.
 * Only what the member owns is offered, each with its rarity (and HD when drawn by the graphics chip); how
 * many more the shop sells is said in one line (#79).
 */
type Tab = "banner" | "frame" | "backdrop" | "background" | "name" | "title" | "badges" | "level";
type DesignSlot = "banner" | "frame" | "background" | "name" | "level";
const SHOP_TYPE: Record<DesignSlot, string> = {
  banner: "profile_banner",
  frame: "avatar_frame",
  background: "profile_background",
  name: "name_style",
  level: "level_badge",
};
const NONE: Partial<Record<DesignSlot, string>> = {
  frame: "none",
  background: "none",
  name: "none",
  level: "classic",
};

/** #79: whether a design of this slot is drawn by the graphics chip */
function isHdLook(slot: DesignSlot, key: string): boolean {
  if (slot === "frame") return Boolean(fxFrameOf(key));
  if (slot === "banner") return key.startsWith("live-") && isHdAmbient(key.slice(5));
  if (slot === "background") return isHdAmbient(key);
  if (slot === "level") return isHdLevelBadge(key);
  if (slot === "name") return Boolean(gpuLook("name_style", key));
  return false;
}

function Choices({
  slot,
  choices,
  current,
  render,
}: {
  slot: DesignSlot;
  choices: LookChoice[];
  current: string | null | undefined;
  render: (key: string) => React.ReactNode;
}) {
  const t = useT();
  const equip = useEquipLook();
  const notify = useNotify();
  // #79: only what the member owns is offered; the rest is counted in one line, toward the shop
  // #99: those won but waiting for a level show too, locked, with what they wait for
  const owned = choices.filter((choice) => !choice.locked || choice.waiting);
  const locked = choices.length - owned.length;
  return (
    <>
      <div className="looks-grid" data-slot={slot}>
        {owned.map((choice) => {
          const selected = (current ?? NONE[slot] ?? null) === choice.key;
          if (choice.waiting) {
            return (
              <div
                key={choice.key}
                className="looks-grid__item"
                data-rarity={choice.rarity ?? undefined}
                data-waiting="true"
              >
                <RarityTag rarity={choice.rarity} />
                <div className="looks-grid__locked">
                  {render(choice.key)}
                  <span className="looks-grid__name">
                    {slot === "background"
                      ? t(`notifications:universe.ambients.${choice.key}`)
                      : slot === "level"
                        ? t(`notifications:levelBadge.names.${choice.key}`)
                        : t(`community:looks.${slot}.${choice.key}`)}
                  </span>
                  <WaitingTag waiting={choice.waiting} />
                </div>
              </div>
            );
          }
          return (
            <div
              key={choice.key}
              className="looks-grid__item"
              data-rarity={choice.rarity ?? undefined}
              data-current={selected || undefined}
            >
              <RarityTag rarity={choice.rarity} />
              <button
                type="button"
                aria-pressed={selected}
                disabled={choice.locked || equip.isPending}
                onClick={() =>
                  equip.mutate(
                    { slot, value: slot === "level" && choice.key === "classic" ? null : choice.key },
                    { onError: () => notify({ severity: "warning", title: t("community:looks.failed") }) },
                  )
                }
              >
                {render(choice.key)}
                <span className="looks-grid__name">
                  {choice.locked ? (
                    <Icon name="lock" size={14} />
                  ) : selected ? (
                    <Icon name="check" size={14} />
                  ) : null}
                  {slot === "background"
                    ? t(`notifications:universe.ambients.${choice.key}`)
                    : slot === "level"
                      ? t(`notifications:levelBadge.names.${choice.key}`)
                      : t(`community:looks.${slot}.${choice.key}`)}
                </span>
                {isHdLook(slot, choice.key) ? <HdTag /> : null}
              </button>
            </div>
          );
        })}
      </div>
      <InShop count={locked} type={SHOP_TYPE[slot]} />
    </>
  );
}

function BackdropPicker({ unlocked, current }: { unlocked: boolean; current: string | null | undefined }) {
  const t = useT();
  const notify = useNotify();
  const equip = useEquipLook();
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<{ id: string; title: string } | null>(null);
  const results = useQuery({
    queryKey: ["media", "backdrop-search", query],
    enabled: unlocked && query.trim().length >= 2,
    queryFn: async () =>
      (await api.GET("/api/v1/media", { params: { query: { q: query.trim() } } })).data?.items
        .filter((item) => item.kind === "movie" || item.kind === "series")
        .slice(0, 12) ?? [],
  });
  const metadata = useQuery({
    queryKey: ["media", "metadata", picked?.id],
    enabled: Boolean(picked),
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/media/{object_id}/metadata", {
          params: { path: { object_id: picked?.id ?? "" } },
        })
      ).data as { backdrop?: string | null },
  });
  if (!unlocked) {
    return (
      <AdminEmpty
        icon="lock"
        title={t("community:looks.backdropLocked")}
        message={t("community:looks.backdropLockedHint")}
        action={
          <Link className="ds-button ds-button--primary" to="/marketplace?type=profile_backdrop">
            <Icon name="shop" size={16} />
            {t("community:looks.toShop")}
          </Link>
        }
      />
    );
  }
  const backdrop = metadata.data?.backdrop ?? null;
  return (
    <div className="backdrop-picker">
      <p className="ds-page-header__context">{t("community:looks.backdropHint")}</p>
      <input
        type="search"
        className="ds-input"
        value={query}
        placeholder={t("community:looks.searchTitle")}
        aria-label={t("community:looks.searchTitle")}
        onChange={(event) => setQuery(event.target.value)}
      />
      {results.data?.length ? (
        <ul className="backdrop-picker__results">
          {results.data.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                aria-pressed={picked?.id === item.id}
                onClick={() => setPicked({ id: item.id, title: item.title })}
              >
                {item.image_id ? (
                  <img src={imageUrl(item.image_id) ?? undefined} alt="" loading="lazy" />
                ) : (
                  <Icon name="film" />
                )}
                <span>
                  {item.title}
                  {item.year ? <span className="admin-muted"> · {item.year}</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : query.trim().length >= 2 && !results.isPending ? (
        <p className="admin-muted">{t("community:looks.noTitle")}</p>
      ) : null}
      {picked ? (
        <div className="backdrop-picker__preview">
          {metadata.isPending ? (
            <Icon name="spinner" className="live-progress__spinner" />
          ) : backdrop ? (
            <>
              <img src={backdropUrl(backdrop, "w780")} alt="" />
              <Button
                variant="primary"
                disabled={equip.isPending}
                onClick={() =>
                  equip.mutate(
                    { slot: "backdrop", value: { object_id: picked.id, ref: backdrop, title: picked.title } },
                    {
                      onSuccess: () => notify({ severity: "success", title: t("community:looks.saved") }),
                      onError: () => notify({ severity: "warning", title: t("community:looks.failed") }),
                    },
                  )
                }
              >
                <Icon name="image" size={16} />
                {t("community:looks.useBackdrop", { title: picked.title })}
              </Button>
            </>
          ) : (
            <p className="admin-muted">{t("community:looks.noBackdrop")}</p>
          )}
        </div>
      ) : null}
      {current ? (
        <Button
          variant="secondary"
          disabled={equip.isPending}
          onClick={() => equip.mutate({ slot: "backdrop", value: null })}
        >
          <Icon name="close" size={16} />
          {t("community:looks.removeBackdrop")}
        </Button>
      ) : null}
    </div>
  );
}

/** One of my titles under my name (or none). */
function TitlePicker({
  titles,
  current,
  inShop,
}: {
  titles: WornItem[];
  current: string | null | undefined;
  inShop: number;
}) {
  const t = useT();
  const equip = useEquipLook();
  if (!titles.length) return <OwnedEmpty type="title" />;
  return (
    <>
      <div className="looks-list">
        {[null, ...titles].map((item) =>
          item?.waiting ? (
            <div key={item.key} className="looks-list__locked" data-waiting="true">
              <WornBadge item={item} kind="title" />
              <ItemTags item={item} />
              <WaitingTag waiting={item.waiting} />
            </div>
          ) : (
            <button
              key={item?.key ?? "none"}
              type="button"
              aria-pressed={(current ?? null) === (item?.key ?? null)}
              disabled={equip.isPending}
              onClick={() => equip.mutate({ slot: "title", value: item?.key ?? null })}
            >
              {item ? <WornBadge item={item} kind="title" /> : t("community:looks.noTitle")}
              {item ? <ItemTags item={item} /> : null}
            </button>
          ),
        )}
      </div>
      <InShop count={inShop} type="title" />
    </>
  );
}

/** Up to three of my badges next to my name. */
function BadgePicker({ badges, current, inShop }: { badges: WornItem[]; current: string[]; inShop: number }) {
  const t = useT();
  const equip = useEquipLook();
  if (!badges.length) return <OwnedEmpty type="badge" />;
  const toggle = (key: string) => {
    const next = current.includes(key) ? current.filter((k) => k !== key) : [...current, key].slice(-3);
    equip.mutate({ slot: "badges", value: next.length ? next : null });
  };
  return (
    <>
      <p className="admin-muted">{t("community:looks.badgesHint")}</p>
      <div className="looks-list">
        {badges.map((item) =>
          item.waiting ? (
            <div key={item.key} className="looks-list__locked" data-waiting="true">
              <WornBadge item={item} kind="badge" />
              <ItemTags item={item} />
              <WaitingTag waiting={item.waiting} />
            </div>
          ) : (
            <button
              key={item.key}
              type="button"
              aria-pressed={current.includes(item.key)}
              disabled={equip.isPending}
              onClick={() => toggle(item.key)}
            >
              <WornBadge item={item} kind="badge" />
              <ItemTags item={item} />
            </button>
          ),
        )}
      </div>
      <InShop count={inShop} type="badge" />
    </>
  );
}

/** #79: a title's or badge's rarity, and HD when drawn by the graphics chip */
function ItemTags({ item }: { item: WornItem }) {
  return (
    <span className="looks-list__tags">
      <RarityTag rarity={item.rarity} />
      {gpuLook("badge", item.style) ? <HdTag /> : null}
    </span>
  );
}

function OwnedEmpty({ type }: { type: "title" | "badge" }) {
  const t = useT();
  return (
    <AdminEmpty
      icon={type === "title" ? "trophy" : "star"}
      title={t(type === "title" ? "community:looks.noTitles" : "community:looks.noBadges")}
      action={
        <Link className="ds-button ds-button--secondary" to={`/marketplace?type=${type}`}>
          <Icon name="shop" size={16} />
          {t("community:looks.toShop")}
        </Link>
      }
    />
  );
}

export function ProfileCustomizer({ name, memberId }: { name: string; memberId: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("banner");
  const looks = useProfileLooks(open);
  const equipped = looks.data?.equipped ?? {};
  const level = useProgression().data?.level ?? 12;
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      size="lg"
      title={t("community:looks.title")}
      description={t("community:looks.description")}
      closeLabel={t("community:looks.close")}
      trigger={
        <Button variant="secondary" className="profile-hero__customize">
          <Icon name="palette" size={16} />
          {t("community:looks.customize")}
        </Button>
      }
    >
      <div className="looks-preview" aria-hidden="true">
        <BannerArt banner={equipped.banner ?? null} backdrop={equipped.backdrop ?? null} />
        <FramedAvatar
          frame={equipped.frame}
          name={name}
          userId={memberId}
          src={`/api/v1/users/${memberId}/avatar`}
          size="lg"
        />
      </div>
      <AdminTabs
        label={t("community:looks.title")}
        current={tab}
        onChange={(key) => setTab(key as Tab)}
        tabs={[
          { key: "banner", label: t("community:looks.tab.banner") },
          { key: "frame", label: t("community:looks.tab.frame") },
          { key: "backdrop", label: t("community:looks.tab.backdrop") },
          { key: "name", label: t("community:looks.tab.name") },
          { key: "title", label: t("community:looks.tab.title") },
          { key: "badges", label: t("community:looks.tab.badges") },
          { key: "level", label: t("community:looks.tab.level") },
        ]}
      />
      {!looks.data ? (
        <Icon name="spinner" className="live-progress__spinner" />
      ) : tab === "banner" ? (
        <>
          {equipped.backdrop ? <p className="admin-muted">{t("community:looks.backdropWins")}</p> : null}
          <Choices
            slot="banner"
            choices={looks.data.banners}
            current={equipped.banner}
            render={(key) => <BannerArt banner={key} />}
          />
        </>
      ) : tab === "frame" ? (
        <Choices
          slot="frame"
          choices={looks.data.frames}
          current={equipped.frame}
          render={(key) => <FramedAvatar frame={key} name={name} userId={memberId} size="md" />}
        />
      ) : tab === "name" ? (
        <Choices
          slot="name"
          choices={looks.data.names}
          current={equipped.name}
          render={(key) => (
            <span className="looks-grid__name-sample">
              <StyledName name={name} style={key} />
            </span>
          )}
        />
      ) : tab === "level" ? (
        <Choices
          slot="level"
          choices={looks.data.levels ?? []}
          current={equipped.level}
          render={(key) => (
            <span className="looks-grid__level">
              <LevelBadge level={level} label={key} look={key} />
            </span>
          )}
        />
      ) : tab === "title" ? (
        <TitlePicker
          titles={looks.data.titles}
          current={equipped.title?.key}
          inShop={looks.data.in_shop?.title ?? 0}
        />
      ) : tab === "badges" ? (
        <BadgePicker
          badges={looks.data.badges}
          current={(equipped.badges?.items ?? []).map((item) => item.key)}
          inShop={looks.data.in_shop?.badge ?? 0}
        />
      ) : (
        <BackdropPicker unlocked={looks.data.backdrop.unlocked} current={equipped.backdrop?.ref} />
      )}
    </Dialog>
  );
}
