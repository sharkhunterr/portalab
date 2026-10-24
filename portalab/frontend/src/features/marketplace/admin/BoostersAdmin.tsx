import { useQuery } from "@tanstack/react-query";
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
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import type { Product } from "../api";
import { type BoosterInfo, boosterOf, localized } from "../boosters/api";
import { ProductPack } from "../boosters/Boosters";
import { CARD_BOOSTER, type SceneBinding } from "../boosters/scene/scene";
import { PoolPicker, PoolSummary, poolNamed, poolPacks, usePoolPreview } from "./BoosterPool";
import { withConfirmation } from "./confirm";
import type { Season } from "./console/api";
import { RARITIES, SEASONS } from "./ProductEditor";

// what a booster draws (the shop's draw rules — not looks): Portalab's looks, the HD ones, the reserve's items
const POOLS = ["looks", "hd", "reserve"] as const;
// a booster's pool may name visual packs (issue 153): what that live pack sells
const VISUAL = "visual:";

/**
 * Issue 153: what a booster may be made of — the sealed packs' looks, the scenes it may open with, the
 * visual packs it may draw from (Portalab's and the imported ones) and which scene each booster wears; all
 * read from the server, none written here.
 */
interface BoosterOptions {
  looks: Array<{ look: string; names: Record<string, string>; pack: string }>;
  scenes: Array<{ pack: string; look: string; names: Record<string, string> }>;
  packs: Array<{ id: string; names: Record<string, string>; products: number }>;
  bindings: Record<string, SceneBinding>;
}

function useBoosterOptions() {
  return useQuery({
    queryKey: ["visuals", "booster-options"],
    queryFn: async () =>
      (await api.GET("/api/v1/admin/visuals/booster-options")).data as unknown as BoosterOptions,
  });
}

interface Draft {
  nameEn: string;
  nameFr: string;
  rarity: string;
  price: string;
  cards: string;
  odds: Record<string, string>;
  guarantee: string;
  refunds: Record<string, string>;
  pool: string;
  season: string;
  perMember: string;
  look: string;
  /** ``pack:look`` of its own scene, or "" (the one every booster wears, else Portalab's) */
  scene: string;
  /** the visual packs it draws from */
  visualPacks: string[];
  /** the shop's packs it draws from */
  shopPacks: string[];
  /** and the items it draws, named one by one */
  items: string[];
}

const whole = (value: string) => Math.max(0, Math.round(Number(value) || 0));

function draftOf(
  product: Product | null,
  info: BoosterInfo | null,
  options: BoosterOptions | undefined,
): Draft {
  const own = product ? options?.bindings[product.key] : undefined;
  const packs = info?.packs ?? [];
  return {
    nameEn: product?.names?.en ?? "",
    nameFr: product?.names?.fr ?? "",
    rarity: product?.rarity ?? "rare",
    price: String(product?.price_coins ?? 300),
    cards: String(info?.cards ?? 5),
    odds: Object.fromEntries(
      RARITIES.map((r) => [
        r,
        String(info?.weights?.[r] ?? { common: 62, rare: 26, epic: 10, legendary: 2 }[r]),
      ]),
    ),
    guarantee: info?.guarantee ?? "common",
    refunds: Object.fromEntries(
      RARITIES.map((r) => [
        r,
        String(info?.refunds[r] ?? { common: 10, rare: 15, epic: 20, legendary: 30 }[r]),
      ]),
    ),
    pool: info?.pool ?? "looks",
    season: info?.season ?? "",
    perMember: info?.per_member ? String(info.per_member) : "",
    look: info?.look ?? options?.looks[0]?.look ?? "",
    scene: own ? `${own.pack}:${own.look}` : "",
    visualPacks: packs.filter((p) => p.startsWith(VISUAL)).map((p) => p.slice(VISUAL.length)),
    shopPacks: packs.filter((p) => !p.startsWith(VISUAL)),
    items: info?.items ?? [],
  };
}

function payloadOf(value: Draft) {
  const packs = poolPacks(value);
  return {
    pool: value.pool,
    cards: Math.min(10, Math.max(1, whole(value.cards))),
    odds: Object.fromEntries(RARITIES.map((r) => [r, whole(value.odds[r] ?? "0")])),
    guarantee: value.guarantee,
    refunds: Object.fromEntries(RARITIES.map((r) => [r, whole(value.refunds[r] ?? "0")])),
    look: value.look,
    ...(value.season ? { season: value.season } : {}),
    ...(packs.length ? { packs } : {}),
    ...(value.items.length ? { items: value.items } : {}),
    ...(whole(value.perMember) ? { per_member: whole(value.perMember) } : {}),
  };
}

/** A key for a new booster, from its name (``booster_<name>``; a number when it is taken). */
function keyFor(name: string, taken: ReadonlySet<string>): string {
  const base = `booster_${
    name
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 40) || "new"
  }`;
  let key = base;
  for (let n = 2; taken.has(key); n += 1) key = `${base}_${n}`;
  return key;
}

const bindScene = (key: string, scene: string) => {
  const [pack, look] = scene ? scene.split(":") : [null, null];
  return api.PUT("/api/v1/admin/visuals/scenes/{booster_key}", {
    params: { path: { booster_key: key } },
    body: { pack: pack ?? null, look: look ?? null },
  });
};

/** The form of a booster — what it is, what it draws, how it looks — to create one or tune it. */
function BoosterForm({
  value,
  patch,
  options,
  products,
  creating,
}: {
  value: Draft;
  patch: (next: Partial<Draft>) => void;
  options: BoosterOptions | undefined;
  products: readonly Product[];
  creating: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const total = RARITIES.reduce((sum, r) => sum + whole(value.odds[r] ?? "0"), 0);
  const name = (names: Record<string, string>, fallback: string) => localized(names, locale) || fallback;
  return (
    <div className="admin-booster__form">
      <fieldset className="product-editor__fields">
        <legend>{t("marketplace:admin.boosters.what")}</legend>
        <TextField
          label={t("marketplace:admin.nameEn")}
          value={value.nameEn}
          required
          onChange={(e) => patch({ nameEn: e.target.value })}
        />
        <TextField
          label={t("marketplace:admin.nameFr")}
          value={value.nameFr}
          onChange={(e) => patch({ nameFr: e.target.value })}
        />
        <SelectField
          label={t("marketplace:admin.rarity")}
          value={value.rarity}
          onChange={(e) => patch({ rarity: e.target.value })}
        >
          {RARITIES.map((r) => (
            <option key={r} value={r}>
              {t(`marketplace:rarity.${r}`)}
            </option>
          ))}
        </SelectField>
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
              {r === "common" ? t("marketplace:admin.boosters.noGuarantee") : t(`marketplace:rarity.${r}`)}
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
      </fieldset>
      <fieldset className="product-editor__fields">
        <legend>{t("marketplace:admin.boosters.looks")}</legend>
        <SelectField
          label={t("marketplace:admin.boosters.look")}
          value={value.look}
          onChange={(e) => patch({ look: e.target.value })}
        >
          {(options?.looks ?? []).map((look) => (
            <option key={look.look} value={look.look}>
              {name(look.names, look.look)}
            </option>
          ))}
          {value.look && !options?.looks.some((l) => l.look === value.look) ? (
            <option value={value.look}>{value.look}</option>
          ) : null}
        </SelectField>
        <SelectField
          label={t("marketplace:admin.boosters.scene")}
          hint={t("marketplace:admin.boosters.sceneHint")}
          value={value.scene}
          onChange={(e) => patch({ scene: e.target.value })}
        >
          <option value="">
            {options?.bindings["*"]
              ? t("marketplace:admin.boosters.sceneAll", {
                  name: name(options.bindings["*"].names, options.bindings["*"].look),
                })
              : t("marketplace:admin.boosters.scenePortalab")}
          </option>
          {(options?.scenes ?? []).map((scene) => (
            <option key={`${scene.pack}:${scene.look}`} value={`${scene.pack}:${scene.look}`}>
              {name(scene.names, scene.look)}
            </option>
          ))}
        </SelectField>
      </fieldset>
      <fieldset className="product-editor__fields">
        <legend>{t("marketplace:admin.boosters.pool")}</legend>
        <SelectField
          label={t("marketplace:admin.boosters.poolKind")}
          value={value.pool}
          onChange={(e) => patch({ pool: e.target.value })}
        >
          {POOLS.map((pool) => (
            <option key={pool} value={pool}>
              {t(`marketplace:booster.pool.${pool}`)}
            </option>
          ))}
        </SelectField>
        <PoolPicker
          value={value}
          patch={patch}
          visualPacks={options?.packs ?? []}
          products={products}
          odds={value.odds}
        />
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
      {creating ? <p className="admin-muted">{t("marketplace:admin.boosters.createHint")}</p> : null}
    </div>
  );
}

/** One booster's settings — what it holds, its odds, what a duplicate gives back, its looks: a new version. */
function BoosterSettings({
  product,
  products,
  onSaved,
  seasons,
  options,
}: {
  product: Product;
  products: readonly Product[];
  onSaved: () => void;
  seasons?: readonly Season[] | undefined;
  options: BoosterOptions | undefined;
}) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const info = boosterOf(product);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const current = info ? draftOf(product, info, options) : null;
  const preview = usePoolPreview(current);
  if (!info || !current) return null;
  const value = draft ?? current;
  const patch = (next: Partial<Draft>) => setDraft({ ...value, ...next });
  const scene = options?.bindings[product.key] ?? options?.bindings["*"];
  const save = async () => {
    setError(null);
    if (!poolNamed(value)) {
      setError(t("marketplace:admin.boosters.poolNeeded"));
      return;
    }
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
                  names: {
                    ...product.names,
                    en: value.nameEn,
                    ...(value.nameFr ? { fr: value.nameFr } : {}),
                  },
                  descriptions: product.descriptions,
                  conditions: product.conditions,
                  refund_policy: product.refund_policy,
                  payload: payloadOf(value),
                },
              } as never,
            })
            .then(({ error: failure }) => {
              if (failure) throw failure;
            }),
        () => window.confirm(t("marketplace:admin.confirm")),
      );
      if (value.rarity !== (product.rarity ?? "common")) {
        await api.PUT("/api/v1/admin/marketplace/products/{key}/presentation", {
          params: { path: { key: product.key } },
          body: {
            presentation: {
              rarity: value.rarity,
              featured: product.featured,
              poster_effect: product.poster_effect,
              icon: product.icon ?? null,
              season: product.season ?? null,
            },
            category: product.category ?? null,
          } as never,
        });
      }
      const before = options?.bindings[product.key];
      if (value.scene !== (before ? `${before.pack}:${before.look}` : ""))
        await bindScene(product.key, value.scene);
      setOpen(false);
      setDraft(null);
      onSaved();
    } catch {
      setError(t("marketplace:admin.error"));
    }
  };
  // the booster leaves the shop (archived: past openings and sealed ones offered keep theirs) — its looks, its
  // scene and the visual packs stay as they are; only what it was made of goes
  const remove = async () => {
    if (!window.confirm(t("marketplace:admin.boosters.deleteConfirm", { name: product.name }))) return;
    setError(null);
    const { error: failure } = await api.POST("/api/v1/admin/marketplace/products/{key}/{transition}", {
      params: { path: { key: product.key, transition: "archive" } },
      body: { confirmation: null },
    });
    if (failure) {
      setError(t("marketplace:admin.error"));
      return;
    }
    if (options?.bindings[product.key]) await bindScene(product.key, "");
    setOpen(false);
    onSaved();
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
          {scene
            ? ` · ${t("marketplace:admin.boosters.wears", { name: localized(scene.names, locale) || scene.look })}`
            : ""}
        </span>
        {info.defined === false ? (
          <span className="admin-booster__undefined">
            <Icon name="warning" size={14} /> {t("marketplace:admin.boosters.undefinedPool")}
          </span>
        ) : null}
        <PoolSummary preview={preview.data} odds={value.odds} />
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
          if (next) setDraft(draftOf(product, info, options));
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
        footer={
          <>
            <Button variant="danger" onClick={remove}>
              <Icon name="trash" size={16} />
              {t("marketplace:admin.boosters.delete")}
            </Button>
            <Button onClick={save}>{t("marketplace:admin.save")}</Button>
          </>
        }
      >
        <BoosterForm value={value} patch={patch} options={options} products={products} creating={false} />
        {error ? <p role="alert">{error}</p> : null}
      </Dialog>
    </li>
  );
}

/** Issue 153: a new booster, made of the visuals there are — created, put on sale, its scene bound. */
function NewBooster({
  taken,
  products,
  options,
  onSaved,
}: {
  taken: ReadonlySet<string>;
  products: readonly Product[];
  options: BoosterOptions | undefined;
  onSaved: () => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const value = draft ?? draftOf(null, null, options);
  const patch = (next: Partial<Draft>) => setDraft({ ...value, ...next });
  const create = async () => {
    setError(null);
    if (!value.nameEn.trim()) {
      setError(t("marketplace:admin.boosters.nameNeeded"));
      return;
    }
    if (!poolNamed(value)) {
      setError(t("marketplace:admin.boosters.poolNeeded"));
      return;
    }
    const key = keyFor(value.nameEn, taken);
    try {
      const created = await api.POST("/api/v1/admin/marketplace/products", {
        body: {
          definition: {
            key,
            type: "booster",
            category: "boosters",
            repeatable: true,
            presentation: { rarity: value.rarity, featured: false, poster_effect: "auto", icon: "sparkles" },
            version: {
              price_coins: whole(value.price),
              conditions: [],
              names: { en: value.nameEn.trim(), ...(value.nameFr.trim() ? { fr: value.nameFr.trim() } : {}) },
              descriptions: {},
              payload: payloadOf(value),
            },
          },
        } as never,
      });
      if (created.error) throw created.error;
      await withConfirmation(
        (confirmation) =>
          api
            .POST("/api/v1/admin/marketplace/products/{key}/{transition}", {
              params: { path: { key, transition: "publish" } },
              body: { confirmation: confirmation ?? null },
            })
            .then(({ error: failure }) => {
              if (failure) throw failure;
            }),
        () => window.confirm(t("marketplace:admin.confirm")),
      );
      if (value.scene) await bindScene(key, value.scene);
      setOpen(false);
      setDraft(null);
      onSaved();
    } catch {
      setError(t("marketplace:admin.error"));
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setDraft(draftOf(null, null, options));
      }}
      size="lg"
      title={t("marketplace:admin.boosters.new")}
      closeLabel={t("marketplace:admin.cancel")}
      trigger={
        <Button>
          <Icon name="plus" size={16} />
          {t("marketplace:admin.boosters.new")}
        </Button>
      }
      footer={<Button onClick={create}>{t("marketplace:admin.boosters.create")}</Button>}
    >
      <BoosterForm value={value} patch={patch} options={options} products={products} creating />
      {error ? <p role="alert">{error}</p> : null}
    </Dialog>
  );
}

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

/**
 * #81: the boosters — each one's odds per rarity, what a duplicate gives back, how many cards and what it
 * draws from (a new version of the product: what was opened before keeps its own). Offering one: a level
 * reward (Engagement › Levels) or an achievement (Engagement › Achievements) gives it sealed. Issue 153: a
 * new one is made here of the visuals there are — its pack's look, its scene, the visual packs it draws from.
 */
/** Issue 243: the scene every Mediacards booster wears (bought or given by watching) — apart from the looks
 * boosters', which they never take. */
function CardBoostersScene({
  options,
  onSaved,
}: {
  options: BoosterOptions | undefined;
  onSaved: () => void;
}) {
  const t = useT();
  const { locale } = useLocaleContext();
  const bound = options?.bindings[CARD_BOOSTER];
  const current = bound ? `${bound.pack}:${bound.look}` : "";
  const [saving, setSaving] = useState(false);
  return (
    <SelectField
      label={t("marketplace:admin.boosters.cardScene")}
      hint={t("marketplace:admin.boosters.cardSceneHint")}
      value={current}
      disabled={saving || !options}
      onChange={async (event) => {
        setSaving(true);
        try {
          await bindScene(CARD_BOOSTER, event.target.value);
          onSaved();
        } finally {
          setSaving(false);
        }
      }}
    >
      <option value="">{t("marketplace:admin.boosters.cardScenePortalab")}</option>
      {(options?.scenes ?? []).map((scene) => (
        <option key={`${scene.pack}:${scene.look}`} value={`${scene.pack}:${scene.look}`}>
          {localized(scene.names, locale) || scene.look}
        </option>
      ))}
    </SelectField>
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
  const options = useBoosterOptions();
  const boosters = products.filter((p) => p.type === "booster" && p.state !== "archived");
  const saved = () => {
    void options.refetch();
    onSaved();
  };
  return (
    <AdminSection
      title={t("marketplace:admin.boosters.title")}
      icon="sparkles"
      actions={
        <NewBooster
          taken={new Set(products.map((p) => p.key))}
          products={products}
          options={options.data}
          onSaved={saved}
        />
      }
    >
      <p className="admin-muted">
        {t("marketplace:admin.boosters.pitch")}{" "}
        <Link to="/admin/gamification">{t("marketplace:admin.boosters.gifts")}</Link>
      </p>
      <CardBoostersScene options={options.data} onSaved={saved} />
      {boosters.length ? (
        <ul className="admin-boosters">
          {boosters.map((product) => (
            <BoosterSettings
              key={product.key}
              product={product}
              products={products}
              onSaved={saved}
              seasons={seasons}
              options={options.data}
            />
          ))}
        </ul>
      ) : (
        <p className="admin-muted">{t("marketplace:admin.boosters.none")}</p>
      )}
    </AdminSection>
  );
}
