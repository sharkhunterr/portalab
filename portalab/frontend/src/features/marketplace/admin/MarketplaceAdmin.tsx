import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { type Category, type Product, useCategories } from "../api";
import { BoostersAdmin } from "./BoostersAdmin";
import { type Season, useSeasons } from "./console/api";
import { CatalogTab } from "./console/CatalogTab";
import { Overview } from "./console/Overview";
import { NewProductDialog } from "./ProductEditor";
import { RaritySupply } from "./RaritySupply";
import { RequestsQueue } from "./RequestsQueue";
import "../marketplace.css";

/**
 * ``/admin/marketplace`` (spec 015 T021, T030; #98): the shop's console, a page each in the Shop hub —
 * the overview (purchases, Coins, the latest activity, the journal), the members (Coins and items given or
 * taken back, their history), the requests to handle, the catalogue a page at a time (with rarities and
 * collections), the boosters and their seasons.
 */
const VIEWS = ["overview", "members", "requests", "catalog", "boosters"] as const;
type View = (typeof VIEWS)[number];
export default function MarketplaceAdmin() {
  const t = useT();
  const client = useQueryClient();
  const canAudit = useHasPermission("marketplace.audit");
  // #98: one page each in the Shop hub (a single level of tabs): /admin/marketplace[/members|…]
  const location = useLocation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const last = location.pathname.split("/").filter(Boolean).at(-1) ?? "";
  const tab: View = VIEWS.includes(last as View) ? (last as View) : "overview";
  const member = params.get("member");
  // admin reorganisation (trial): a member's balances, items and history live on their card
  const toMember = (id: string) => navigate(`/admin/members/${encodeURIComponent(id)}?tab=economy`);
  // the whole catalogue only where it is needed (a pack's contents, the boosters): never drawn at once
  const products = useQuery({
    queryKey: ["marketplace", "admin", "products"],
    enabled: tab === "catalog" || tab === "boosters",
    queryFn: async () => (await api.GET("/api/v1/admin/marketplace/products")).data ?? [],
  });
  const audit = useQuery({
    queryKey: ["marketplace", "admin", "audit"],
    enabled: canAudit && tab === "overview",
    queryFn: async () => (await api.GET("/api/v1/admin/marketplace/audit")).data?.items ?? [],
  });
  const seasons = useSeasons();
  const categories = useCategories();
  const [collectionKey, setCollectionKey] = useState("");
  const [collectionName, setCollectionName] = useState("");
  const refresh = () => client.invalidateQueries({ queryKey: ["marketplace"] });
  const [message, setMessage] = useState<string | null>(null);
  const run = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setMessage(t("marketplace:admin.done"));
      client.invalidateQueries({ queryKey: ["marketplace"] });
    },
    onError: () => setMessage(t("marketplace:admin.error")),
  });
  return (
    <AdminPage
      icon="shop"
      title={t(`marketplace:shopadmin.view.${tab}.title`)}
      description={t(`marketplace:shopadmin.view.${tab}.description`)}
      wide
      primary={
        tab === "catalog" ? (
          <NewProductDialog
            categories={(categories.data ?? []) as Category[]}
            products={(products.data ?? []) as Product[]}
            onCreated={refresh}
          />
        ) : undefined
      }
    >
      {message ? <p role="status">{message}</p> : null}
      {tab === "overview" ? <Overview onMember={toMember} /> : null}
      {tab === "members" ? (
        <Navigate
          to={member ? `/admin/members/${encodeURIComponent(member)}?tab=economy` : "/admin/members"}
          replace
        />
      ) : null}
      {tab === "requests" ? <RequestsQueue /> : null}
      {tab === "catalog" ? <CatalogTab categories={(categories.data ?? []) as Category[]} /> : null}
      {tab === "catalog" ? <RaritySupply /> : null}
      {tab === "boosters" ? (
        <>
          <SeasonsStrip seasons={seasons.data ?? []} />
          <BoostersAdmin
            products={(products.data ?? []) as Product[]}
            onSaved={refresh}
            seasons={seasons.data}
          />
        </>
      ) : null}
      {tab === "catalog" ? (
        <>
          <AdminSection title={t("marketplace:shop.byCollection")} icon="star">
            <ul className="admin-collections">
              {((categories.data ?? []) as Category[]).map((c) => (
                <li key={c.key} className="ds-badge">
                  <Icon name={c.icon ?? "star"} size={14} /> {t(c.label_key)}
                </li>
              ))}
            </ul>
            <div className="ds-stack ds-stack--row">
              <TextField
                label={t("marketplace:admin.collectionKey")}
                value={collectionKey}
                pattern="[a-z][a-z0-9_]*"
                onChange={(e) => setCollectionKey(e.target.value)}
              />
              <TextField
                label={t("marketplace:admin.collectionName")}
                value={collectionName}
                onChange={(e) => setCollectionName(e.target.value)}
              />
              <Button
                variant="secondary"
                disabled={!collectionKey || !collectionName}
                onClick={() =>
                  run.mutate(async () => {
                    await api.POST("/api/v1/admin/marketplace/categories", {
                      body: { key: collectionKey, label_key: collectionName, position: 100 },
                    });
                    setCollectionKey("");
                    setCollectionName("");
                  })
                }
              >
                <Icon name="plus" size={18} />
                {t("marketplace:admin.newCollection")}
              </Button>
            </div>
          </AdminSection>
        </>
      ) : null}
      {tab === "overview" && canAudit ? (
        <AdminSection title={t("marketplace:admin.audit")} icon="settings">
          <ul className="ds-stack">
            {(audit.data ?? []).map((entry) => (
              <li key={String(entry.id)}>
                {String(entry.occurred_at)} · {String(entry.action)} · {String(entry.resource_type ?? "")}{" "}
                {String(entry.resource_id ?? "")}
              </li>
            ))}
          </ul>
        </AdminSection>
      ) : null}
    </AdminPage>
  );
}

/** #98: the seasons' weeks — a season's booster is in the shop in them only. */
function SeasonsStrip({ seasons }: { seasons: readonly Season[] }) {
  const t = useT();
  if (!seasons.length) return null;
  const when = (md: readonly number[]) =>
    `${String(md[1]).padStart(2, "0")}/${String(md[0]).padStart(2, "0")}`;
  return (
    <AdminSection
      title={t("marketplace:shopadmin.seasons")}
      icon="calendar"
      description={t("marketplace:shopadmin.seasonsHint")}
    >
      <ul className="mk-seasons">
        {seasons.map((season) => (
          <li key={season.key} data-now={season.now || undefined}>
            <strong>{t(`marketplace:season.${season.key}`)}</strong>
            <small>
              {when(season.start)} → {when(season.end)}
              {season.now ? ` · ${t("marketplace:shopadmin.season.nowShort")}` : ""}
            </small>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}
