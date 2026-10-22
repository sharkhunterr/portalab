import { useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type MediaCard, type Rarity, useCardPool } from "./api";
import { Binder } from "./SetPage";

const RARITIES: Rarity[] = ["legendary", "epic", "rare", "common"];
const KINDS: MediaCard["kind"][] = ["title", "cast", "director", "creator", "writer", "composer"];

/** Issue 229: every card there is (the pool), the rarest first — by name, rarity, kind, country, or mine. */
export function PoolView() {
  const t = useT();
  const format = useFormat();
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
      <div className="cards-filters">
        <input
          type="search"
          value={q}
          placeholder={t("gamification:cards.pool.search")}
          aria-label={t("gamification:cards.pool.search")}
          onChange={(event) => reset(setQ)(event.target.value)}
        />
        <select
          value={rarity}
          aria-label={t("gamification:cards.pool.rarity")}
          onChange={(event) => reset(setRarity)(event.target.value as Rarity | "")}
        >
          <option value="">{t("gamification:cards.pool.anyRarity")}</option>
          {RARITIES.map((r) => (
            <option key={r} value={r}>
              {t(`gamification:cards.rarity.${r}`)}
            </option>
          ))}
        </select>
        <select
          value={kind}
          aria-label={t("gamification:cards.pool.kind")}
          onChange={(event) => reset(setKind)(event.target.value as MediaCard["kind"] | "")}
        >
          <option value="">{t("gamification:cards.pool.anyKind")}</option>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`gamification:cards.kind.${k}`)}
            </option>
          ))}
        </select>
        <select
          value={country}
          aria-label={t("gamification:cards.pool.country")}
          onChange={(event) => reset(setCountry)(event.target.value)}
        >
          <option value="">{t("gamification:cards.pool.anyCountry")}</option>
          {(pool.data?.countries ?? []).map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label>
          <input
            type="checkbox"
            checked={owned}
            onChange={(event) => reset(setOwned)(event.target.checked)}
          />
          {t("gamification:cards.pool.mine")}
        </label>
      </div>
      <p className="admin-muted">
        {t("gamification:cards.pool.count", { count: format.number(pool.data?.total ?? 0) })}
      </p>
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
