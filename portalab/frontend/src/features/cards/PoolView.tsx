import { useState } from "react";
import { CheckboxField, SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { type MediaCard, type Rarity, useCardPool } from "./api";
import { Binder } from "./SetPage";

const RARITIES: Rarity[] = ["legendary", "epic", "rare", "common"];
const KINDS: MediaCard["kind"][] = ["title", "cast", "director", "creator", "writer", "composer"];

/** Issue 229: every card there is (the pool), the rarest first — by name, rarity, kind, country, or mine.
 * issue 298: the site's own fields (as the media catalog), the rarities as pills. */
export function PoolView() {
  const t = useT();
  const [q, setQ] = useState("");
  const [rarity, setRarity] = useState<Rarity | "">("");
  const [kind, setKind] = useState<MediaCard["kind"] | "">("");
  const [country, setCountry] = useState("");
  const [owned, setOwned] = useState(false);
  const [page, setPage] = useState(0);
  const pool = useCardPool({ q, rarity, kind, country, owned, page });
  const pages = Math.max(1, Math.ceil((pool.data?.total ?? 0) / 48));
  const reset =
    <T,>(set: (value: T) => void) =>
    (value: T) => {
      set(value);
      setPage(0);
    };
  return (
    <div className="ds-stack">
      <search className="cards-pool">
        <div className="cards-pool__bar">
          <TextField
            label={t("gamification:cards.pool.search")}
            type="search"
            value={q}
            onChange={(event) => reset(setQ)(event.target.value)}
          />
          <SelectField
            label={t("gamification:cards.pool.kind")}
            value={kind}
            onChange={(event) => reset(setKind)(event.target.value as MediaCard["kind"] | "")}
          >
            <option value="">{t("gamification:cards.pool.anyKind")}</option>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`gamification:cards.kind.${k}`)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label={t("gamification:cards.pool.country")}
            value={country}
            onChange={(event) => reset(setCountry)(event.target.value)}
          >
            <option value="">{t("gamification:cards.pool.anyCountry")}</option>
            {(pool.data?.countries ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </SelectField>
        </div>
        <fieldset className="cards-pool__rarities">
          <legend className="visually-hidden">{t("gamification:cards.pool.rarity")}</legend>
          {(["", ...RARITIES] as const).map((r) => (
            <button
              key={r || "any"}
              type="button"
              data-rarity={r || undefined}
              aria-pressed={rarity === r}
              onClick={() => reset(setRarity)(r)}
            >
              {r ? t(`gamification:cards.rarity.${r}`) : t("gamification:cards.pool.anyRarity")}
            </button>
          ))}
        </fieldset>
        <CheckboxField
          label={t("gamification:cards.pool.mine")}
          checked={owned}
          onChange={(event) => reset(setOwned)(event.target.checked)}
        />
      </search>
      <p className="admin-muted">{t("gamification:cards.pool.count", { count: pool.data?.total ?? 0 })}</p>
      <Binder cards={pool.data?.items ?? []} />
      {pages > 1 ? (
        <nav className="cards-pages" aria-label={t("gamification:cards.pages")}>
          <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>
            <Icon name="chevron-left" size={16} />
          </button>
          <span>
            {page + 1} / {pages}
          </span>
          <button type="button" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
            <Icon name="chevron-right" size={16} />
          </button>
        </nav>
      ) : null}
    </div>
  );
}
