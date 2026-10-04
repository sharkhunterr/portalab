import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { AdminGrid, AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { type Category, type Product, useCategories } from "../api";
import { ProductPoster } from "../catalog/ProductPoster";
import { NewProductDialog, PresentationDialog } from "./ProductEditor";
import "../marketplace.css";
import { withConfirmation } from "./confirm";

/**
 * ``/admin/marketplace`` (spec 015 T021, T030): products (JSON definition, versions, publish/archive),
 * grants, revocations with an enumerated ground, and the marketplace audit trail.
 */
export default function MarketplaceAdmin() {
  const t = useT();
  const client = useQueryClient();
  const canAudit = useHasPermission("marketplace.audit");
  const products = useQuery({
    queryKey: ["marketplace", "admin", "products"],
    queryFn: async () => (await api.GET("/api/v1/admin/marketplace/products")).data ?? [],
  });
  const audit = useQuery({
    queryKey: ["marketplace", "admin", "audit"],
    enabled: canAudit,
    queryFn: async () => (await api.GET("/api/v1/admin/marketplace/audit")).data?.items ?? [],
  });
  const categories = useCategories();
  const [collectionKey, setCollectionKey] = useState("");
  const [collectionName, setCollectionName] = useState("");
  const refresh = () => client.invalidateQueries({ queryKey: ["marketplace"] });
  const [grantUser, setGrantUser] = useState("");
  const [grantProduct, setGrantProduct] = useState("");
  const [revokeId, setRevokeId] = useState("");
  const [ground, setGround] = useState("withdrawn_for_cause");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const confirm = () => window.confirm(t("marketplace:admin.confirm"));
  const run = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setMessage(t("marketplace:admin.done"));
      client.invalidateQueries({ queryKey: ["marketplace"] });
    },
    onError: () => setMessage(t("marketplace:admin.error")),
  });
  const move = (key: string, transition: "publish" | "unavailable" | "archive") =>
    run.mutate(() =>
      withConfirmation(
        (confirmation) =>
          api.POST("/api/v1/admin/marketplace/products/{key}/{transition}", {
            params: { path: { key, transition } },
            body: { confirmation: confirmation ?? null },
          }),
        confirm,
      ),
    );
  return (
    <AdminPage
      icon="shop"
      title={t("marketplace:admin.title")}
      description={t("marketplace:admin.description")}
      primary={<NewProductDialog categories={(categories.data ?? []) as Category[]} onCreated={refresh} />}
    >
      {message ? <p role="status">{message}</p> : null}
      <AdminSection title={t("marketplace:admin.products")} icon="shop">
        {products.isError ? <FunctionalState state="unavailable" /> : null}
        <ul className="admin-products">
          {((products.data ?? []) as Product[]).map((p) => (
            <li key={p.key} className="admin-product" data-rarity={p.rarity ?? "common"}>
              <ProductPoster product={p} />
              <div className="admin-product__body">
                <strong>{p.name}</strong>
                <span className="widget__meta">
                  {t(`marketplace:type.${p.type}`)} · {t(`marketplace:rarity.${p.rarity ?? "common"}`)} · v
                  {p.version}
                  {p.price_coins ? ` · ${p.price_coins} Coins` : ""}
                </span>
                <span className="ds-badge" data-state={p.state}>
                  {t(`marketplace:productState.${p.state}`)}
                  {p.featured ? ` · ${t("marketplace:shop.featured")}` : ""}
                </span>
              </div>
              <div className="admin-product__actions">
                <PresentationDialog
                  product={p}
                  categories={(categories.data ?? []) as Category[]}
                  onSaved={refresh}
                />
                {p.state !== "available" && p.state !== "archived" ? (
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={t("marketplace:admin.publish")}
                    title={t("marketplace:admin.publish")}
                    onClick={() => move(p.key, "publish")}
                  >
                    <Icon name="check" size={18} />
                  </Button>
                ) : null}
                {p.state === "available" ? (
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={t("marketplace:admin.unavailable")}
                    title={t("marketplace:admin.unavailable")}
                    onClick={() => move(p.key, "unavailable")}
                  >
                    <Icon name="hide" size={18} />
                  </Button>
                ) : null}
                {p.state !== "archived" ? (
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={t("marketplace:admin.archive")}
                    title={t("marketplace:admin.archive")}
                    onClick={() => move(p.key, "archive")}
                  >
                    <Icon name="trash" size={18} />
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </AdminSection>
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
      <AdminGrid>
        <AdminSection title={t("marketplace:admin.grants")} icon="coins">
          <TextField
            label={t("marketplace:admin.user")}
            value={grantUser}
            onChange={(e) => setGrantUser(e.target.value)}
          />
          <TextField
            label={t("marketplace:admin.product")}
            value={grantProduct}
            onChange={(e) => setGrantProduct(e.target.value)}
          />
          <TextField
            label={t("marketplace:admin.reason")}
            value={reason}
            maxLength={500}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            disabled={!grantUser || !grantProduct || !reason}
            onClick={() =>
              run.mutate(() =>
                withConfirmation(
                  (confirmation) =>
                    api.POST("/api/v1/admin/marketplace/grants", {
                      body: {
                        user_id: grantUser,
                        product: grantProduct,
                        reason,
                        confirmation: confirmation ?? null,
                      },
                    }),
                  confirm,
                ),
              )
            }
          >
            {t("marketplace:admin.grant")}
          </Button>
        </AdminSection>
        <AdminSection title={t("marketplace:admin.revocations")} icon="list">
          <TextField
            label={t("marketplace:admin.ownership")}
            value={revokeId}
            onChange={(e) => setRevokeId(e.target.value)}
          />
          <SelectField
            label={t("marketplace:admin.ground")}
            value={ground}
            onChange={(e) => setGround(e.target.value)}
          >
            {(["abuse", "grant_expired", "refund", "withdrawn_for_cause"] as const).map((g) => (
              <option key={g} value={g}>
                {t(`marketplace:ground.${g}`)}
              </option>
            ))}
          </SelectField>
          <Button
            disabled={!revokeId || !reason}
            onClick={() =>
              run.mutate(() =>
                withConfirmation(
                  (confirmation) =>
                    api.POST("/api/v1/admin/marketplace/ownerships/{ownership_id}/revoke", {
                      params: { path: { ownership_id: revokeId } },
                      body: { ground: ground as "abuse", reason, confirmation: confirmation ?? null },
                    }),
                  confirm,
                ),
              )
            }
          >
            {t("marketplace:admin.revoke")}
          </Button>
        </AdminSection>
      </AdminGrid>
      {canAudit ? (
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
