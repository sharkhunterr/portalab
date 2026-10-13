import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Product } from "../api";
import { type BoosterInfo, boosterOf } from "../boosters/api";
import { ProductPack } from "../boosters/Boosters";
import { withConfirmation } from "./confirm";
import type { Season } from "./console/api";
import { RARITIES, SEASONS } from "./ProductEditor";

const POOLS = ["looks", "hd", "reserve"] as const;
const LOOKS = [
  "cosmos",
  "legend",
  "prestige",
  "reserve",
  "discovery",
  "valentine",
  "spring",
  "summer",
  "halloween",
  "winter",
] as const;

interface Draft {
  price: string;
  cards: string;
  odds: Record<string, string>;
  guarantee: string;
  refunds: Record<string, string>;
  pool: string;
  season: string;
  perMember: string;
  look: string;
}

function draftOf(product: Product, info: BoosterInfo): Draft {
  return {
    price: String(product.price_coins ?? 0),
    cards: String(info.cards),
    odds: Object.fromEntries(RARITIES.map((r) => [r, String(info.weights?.[r] ?? 0)])),
    guarantee: info.guarantee,
    refunds: Object.fromEntries(RARITIES.map((r) => [r, String(info.refunds[r] ?? 0)])),
    pool: info.pool,
    season: info.season ?? "",
    perMember: info.per_member ? String(info.per_member) : "",
    look: info.look,
  };
}

const whole = (value: string) => Math.max(0, Math.round(Number(value) || 0));

/** One booster's settings — what it holds, its odds, what a duplicate gives back: a new version. */
function BoosterSettings({
  product,
  onSaved,
  seasons,
}: {
  product: Product;
  onSaved: () => void;
  seasons?: readonly Season[] | undefined;
}) {
  const t = useT();
  const format = useFormat();
  const info = boosterOf(product);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState(false);
  if (!info) return null;
  const value = draft ?? draftOf(product, info);
  const total = RARITIES.reduce((sum, r) => sum + whole(value.odds[r] ?? "0"), 0);
  const patch = (next: Partial<Draft>) => setDraft({ ...value, ...next });
  const save = async () => {
    setError(false);
    try {
      await withConfirmation(
        (confirmation) =>
          api
            .PUT("/api/v1/admin/marketplace/products/{key}", {
              params: { path: { key: product.key } },
              body: {
                confirmation: confirmation ?? null,
                definition: {
                  price_coins: whole(value.price) || null,
                  names: product.names,
                  descriptions: product.descriptions,
                  conditions: product.conditions,
                  refund_policy: product.refund_policy,
                  payload: {
                    pool: value.pool,
                    cards: Math.min(10, Math.max(1, whole(value.cards))),
                    odds: Object.fromEntries(RARITIES.map((r) => [r, whole(value.odds[r] ?? "0")])),
                    guarantee: value.guarantee,
                    refunds: Object.fromEntries(RARITIES.map((r) => [r, whole(value.refunds[r] ?? "0")])),
                    look: value.look,
                    ...(value.season ? { season: value.season } : {}),
                    ...(whole(value.perMember) ? { per_member: whole(value.perMember) } : {}),
                  },
                },
              } as never,
            })
            .then(({ error: failure }) => {
              if (failure) throw failure;
            }),
        () => window.confirm(t("marketplace:admin.confirm")),
      );
      setOpen(false);
      setDraft(null);
      onSaved();
    } catch {
      setError(true);
    }
  };
  return (
    <li className="admin-booster" data-rarity={product.rarity ?? "common"}>
      <span className="admin-booster__pack">
        <ProductPack product={product} size="mini" />
      </span>
      <div className="admin-booster__body">
        <strong>{product.name}</strong>
        <SeasonState season={info.season ? seasons?.find((s) => s.key === info.season) : undefined} />
        <span className="widget__meta">
          {t(`marketplace:booster.pool.${info.pool}`)}
          {info.season ? ` · ${t(`marketplace:season.${info.season}`)}` : ""} ·{" "}
          {t("marketplace:booster.cards", { count: info.cards })} · {format.number(product.price_coins ?? 0)}{" "}
          Coins
        </span>
        <span className="admin-booster__odds">
          {RARITIES.filter((r) => (info.odds[r] ?? 0) > 0).map((r) => (
            <span key={r} data-rarity={r}>
              {t(`marketplace:rarity.${r}`)} {format.number(info.odds[r] ?? 0)} % · +{info.refunds[r]}
            </span>
          ))}
        </span>
      </div>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (next) setDraft(draftOf(product, info));
        }}
        size="lg"
        title={`${t("marketplace:admin.boosters.edit")} · ${product.name}`}
        closeLabel={t("marketplace:admin.cancel")}
        trigger={
          <Button variant="secondary">
            <Icon name="sliders" size={16} />
            {t("marketplace:admin.boosters.tune")}
          </Button>
        }
        footer={<Button onClick={save}>{t("marketplace:admin.save")}</Button>}
      >
        <div className="admin-booster__form">
          <fieldset className="product-editor__fields">
            <legend>{t("marketplace:admin.boosters.what")}</legend>
            <TextField
              label={t("marketplace:sheet.price")}
              type="number"
              min={1}
              value={value.price}
              onChange={(e) => patch({ price: e.target.value })}
            />
            <TextField
              label={t("marketplace:admin.boosters.cards")}
              type="number"
              min={1}
              max={10}
              value={value.cards}
              onChange={(e) => patch({ cards: e.target.value })}
            />
            <SelectField
              label={t("marketplace:admin.boosters.pool")}
              value={value.pool}
              onChange={(e) => patch({ pool: e.target.value })}
            >
              {POOLS.map((pool) => (
                <option key={pool} value={pool}>
                  {t(`marketplace:booster.pool.${pool}`)}
                </option>
              ))}
            </SelectField>
            <SelectField
              label={t("marketplace:admin.season")}
              value={value.season}
              onChange={(e) => patch({ season: e.target.value })}
            >
              <option value="">{t("marketplace:admin.boosters.allYear")}</option>
              {SEASONS.map((season) => (
                <option key={season} value={season}>
                  {t(`marketplace:season.${season}`)}
                </option>
              ))}
            </SelectField>
            <SelectField
              label={t("marketplace:admin.boosters.guarantee")}
              value={value.guarantee}
              onChange={(e) => patch({ guarantee: e.target.value })}
            >
              {RARITIES.map((r) => (
                <option key={r} value={r}>
                  {r === "common"
                    ? t("marketplace:admin.boosters.noGuarantee")
                    : t(`marketplace:rarity.${r}`)}
                </option>
              ))}
            </SelectField>
            <TextField
              label={t("marketplace:admin.boosters.perMember")}
              hint={t("marketplace:admin.boosters.perMemberHint")}
              type="number"
              min={0}
              value={value.perMember}
              onChange={(e) => patch({ perMember: e.target.value })}
            />
            <SelectField
              label={t("marketplace:admin.boosters.look")}
              value={value.look}
              onChange={(e) => patch({ look: e.target.value })}
            >
              {LOOKS.map((look) => (
                <option key={look} value={look}>
                  {look}
                </option>
              ))}
            </SelectField>
          </fieldset>
          <fieldset className="product-editor__fields admin-booster__table">
            <legend>{t("marketplace:admin.boosters.odds")}</legend>
            <p className="admin-muted">{t("marketplace:admin.boosters.oddsHint")}</p>
            {RARITIES.map((r) => (
              <div key={r} className="admin-booster__row" data-rarity={r}>
                <span className="admin-booster__rarity">{t(`marketplace:rarity.${r}`)}</span>
                <TextField
                  label={t("marketplace:admin.boosters.weight")}
                  type="number"
                  min={0}
                  value={value.odds[r] ?? "0"}
                  onChange={(e) => patch({ odds: { ...value.odds, [r]: e.target.value } })}
                />
                <span className="admin-booster__percent">
                  {total ? format.number(Math.round((whole(value.odds[r] ?? "0") * 1000) / total) / 10) : 0} %
                </span>
                <TextField
                  label={t("marketplace:admin.boosters.refund")}
                  type="number"
                  min={0}
                  value={value.refunds[r] ?? "0"}
                  onChange={(e) => patch({ refunds: { ...value.refunds, [r]: e.target.value } })}
                />
              </div>
            ))}
          </fieldset>
        </div>
        {error ? <p role="alert">{t("marketplace:admin.error")}</p> : null}
      </Dialog>
    </li>
  );
}

/**
 * #81: the boosters — each one's odds per rarity, what a duplicate gives back, how many cards and what it
 * draws from (a new version of the product: what was opened before keeps its own). Offering one: a level
 * reward (Engagement › Levels) or an achievement (Engagement › Achievements) gives it sealed.
 */
/** #98: a season's booster is on sale in its weeks only — whether it is now, else when it will be. */
function SeasonState({ season }: { season: Season | undefined }) {
  const t = useT();
  if (!season) return null;
  const when = (md: readonly number[]) =>
    `${String(md[1]).padStart(2, "0")}/${String(md[0]).padStart(2, "0")}`;
  return (
    <span className="admin-booster__season" data-now={season.now || undefined}>
      {season.now
        ? t("marketplace:shopadmin.season.now")
        : t("marketplace:shopadmin.season.later", { start: when(season.start), end: when(season.end) })}
    </span>
  );
}

export function BoostersAdmin({
  products,
  onSaved,
  seasons,
}: {
  products: readonly Product[];
  onSaved: () => void;
  seasons?: readonly Season[] | undefined;
}) {
  const t = useT();
  const boosters = products.filter((p) => p.type === "booster" && p.state !== "archived");
  return (
    <AdminSection title={t("marketplace:admin.boosters.title")} icon="sparkles">
      <p className="admin-muted">
        {t("marketplace:admin.boosters.pitch")}{" "}
        <Link to="/admin/gamification">{t("marketplace:admin.boosters.gifts")}</Link>
      </p>
      {boosters.length ? (
        <ul className="admin-boosters">
          {boosters.map((product) => (
            <BoosterSettings key={product.key} product={product} onSaved={onSaved} seasons={seasons} />
          ))}
        </ul>
      ) : (
        <p className="admin-muted">{t("marketplace:admin.boosters.none")}</p>
      )}
    </AdminSection>
  );
}
