import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { AdminEmpty, AdminTabs } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useNotify } from "../../../design-system/components/Notification";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { imageUrl } from "../../media/api";
import { backdropUrl, type LookChoice, useEquipLook, useProfileLooks } from "./looks";
import { BannerArt, FramedAvatar } from "./ProfileHero";

/**
 * Profile customisation (027), Steam-like: the banner (free designs, those bought in the shop or in a
 * theme pack), the avatar frame, and — once unlocked in the shop, for every compatible title — the backdrop
 * of a film or a series as the banner. Locked designs show a padlock and lead to the shop.
 */
type Tab = "banner" | "frame" | "backdrop";

function Choices({
  slot,
  choices,
  current,
  render,
}: {
  slot: "banner" | "frame";
  choices: LookChoice[];
  current: string | null | undefined;
  render: (key: string) => React.ReactNode;
}) {
  const t = useT();
  const equip = useEquipLook();
  const notify = useNotify();
  return (
    <div className="looks-grid" data-slot={slot}>
      {choices.map((choice) => {
        const selected = (current ?? (slot === "frame" ? "none" : null)) === choice.key;
        return (
          <div key={choice.key} className="looks-grid__item" data-locked={choice.locked || undefined}>
            <button
              type="button"
              aria-pressed={selected}
              disabled={choice.locked || equip.isPending}
              onClick={() =>
                equip.mutate(
                  { slot, value: choice.key },
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
                {t(`community:looks.${slot}.${choice.key}`)}
              </span>
            </button>
            {choice.locked ? (
              <Link
                className="looks-grid__shop"
                to={`/marketplace?type=${slot === "banner" ? "profile_banner" : "avatar_frame"}`}
              >
                {t("community:looks.inShop")}
              </Link>
            ) : null}
          </div>
        );
      })}
    </div>
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

export function ProfileCustomizer({ name, memberId }: { name: string; memberId: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("banner");
  const looks = useProfileLooks(open);
  const equipped = looks.data?.equipped ?? {};
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
      ) : (
        <BackdropPicker unlocked={looks.data.backdrop.unlocked} current={equipped.backdrop?.ref} />
      )}
    </Dialog>
  );
}
