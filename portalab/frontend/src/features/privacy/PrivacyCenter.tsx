import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { DataRegion } from "../../state/regions";
import { SettingsCard, SettingsGrid } from "../account/SettingsKit";
import { DeletionSection, ExportSection } from "../auth/AccountPage";
import { TermsCard } from "../terms/TermsViewer";
import { type LevelKey, privacyStrings as t } from "./strings";
import "./privacy.css";

type Inventory = components["schemas"]["PrivacyInventory"];
type Datum = Inventory["data"][number];

const KEY = ["privacy", "me"];
const LEVELS: LevelKey[] = ["public", "community", "leaderboard", "private"];
const LEVEL_ICONS: Record<string, string> = {
  public: "globe",
  community: "users",
  leaderboard: "medal",
  private: "lock",
};
const OWNER_ICONS: Record<string, string> = {
  community: "users",
  events: "activity",
  media: "film",
  identity: "user",
  gamification: "trophy",
  statistics: "chart",
  marketplace: "shop",
  support: "lifebuoy",
};

const ownerOf = (item: Datum) => item.owner.replace(/^module:/, "");

/** One datum: what it is, how long it is kept, and who sees it — chosen here when the member may. */
function DatumRow({ item }: { item: Datum }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: async (level: LevelKey) =>
      api.PUT("/api/v1/me/privacy/visibility/{datum_class}", {
        params: { path: { datum_class: item.datum_class } },
        body: { level },
      }),
    onSuccess: (result) => {
      setMessage(result.error ? t.genericError : t.saved);
      void queryClient.invalidateQueries({ queryKey: KEY });
    },
    onError: () => setMessage(t.genericError),
  });
  const level = item.effective_level as LevelKey;
  const name = item.description || item.datum_class;
  return (
    <li className="privacy-datum" data-level={level}>
      <span className="privacy-datum__level" aria-hidden="true">
        <Icon name={LEVEL_ICONS[level] ?? "eye"} size={16} />
      </span>
      <span className="privacy-datum__text">
        <strong>{name}</strong>
        <span className="privacy-datum__badges">
          <span className="ds-badge">{t.kinds[item.classification] ?? item.classification}</span>
          <span className="ds-badge">
            <Icon name="clock" size={12} />
            {item.retention_days ? t.retentionDays(item.retention_days) : t.retentionNone}
          </span>
        </span>
        {item.locked_by_policy ? <span className="privacy-datum__lock">{t.locked}</span> : null}
        {message ? (
          <span role="status" className="privacy-datum__saved">
            {message}
          </span>
        ) : null}
      </span>
      {item.user_choosable && !item.locked_by_policy ? (
        <select
          className="privacy-datum__select"
          aria-label={t.chooseVisibility(name)}
          value={level}
          disabled={change.isPending}
          onChange={(event) => change.mutate(event.target.value as LevelKey)}
        >
          {LEVELS.map((value) => (
            <option key={value} value={value}>
              {t.levels[value]}
            </option>
          ))}
        </select>
      ) : (
        <span className="privacy-datum__fixed">
          {item.locked_by_policy ? <Icon name="lock" size={12} /> : null}
          {t.levels[level] ?? item.effective_level}
        </span>
      )}
    </li>
  );
}

/** "Profile / Data Center" (CD-016; 027 redesign): who sees what at a glance, the data grouped by the part
 * of the portal that keeps it — visibility chosen in place when allowed, admin locks explained — then a
 * copy of my data and the account deletion. */
export function PrivacyCenter() {
  return (
    <DataRegion<Inventory>
      label={t.centerTitle}
      queryKey={KEY}
      queryFn={async () => (await api.GET("/api/v1/me/privacy")).data as Inventory}
    >
      {(inventory) => {
        const groups = new Map<string, Datum[]>();
        for (const item of inventory.data) {
          const owner = ownerOf(item);
          groups.set(owner, [...(groups.get(owner) ?? []), item]);
        }
        return (
          <div className="settings-page privacy-page">
            <PageHeader level={2} icon="shield" title={t.centerTitle} context={t.centerIntro} />
            <ul className="privacy-summary" aria-label={t.summary}>
              {LEVELS.map((level) => (
                <li key={level} data-level={level}>
                  <Icon name={LEVEL_ICONS[level] ?? "eye"} size={18} />
                  <strong>{inventory.data.filter((d) => d.effective_level === level).length}</strong>
                  <span>{t.levelHints[level]}</span>
                </li>
              ))}
            </ul>
            <SettingsGrid>
              {[...groups.entries()].map(([owner, items]) => (
                <SettingsCard
                  key={owner}
                  icon={OWNER_ICONS[owner] ?? "database"}
                  title={t.owners[owner] ?? owner}
                >
                  <ul className="privacy-data">
                    {items.map((item) => (
                      <DatumRow key={item.datum_class} item={item} />
                    ))}
                  </ul>
                </SettingsCard>
              ))}
            </SettingsGrid>
            <section className="privacy-mine" aria-label={t.yourData} id="delete-account">
              <h3>{t.yourData}</h3>
              <p className="ds-page-header__context">{t.yourDataHint}</p>
              <SettingsGrid>
                <TermsCard />
                <ExportSection />
                <DeletionSection />
              </SettingsGrid>
            </section>
          </div>
        );
      }}
    </DataRegion>
  );
}
