import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AdminSection, FormActions } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLevelCurve, usePublishCurve } from "../api";
import { type LevelReward, type ShopProduct, useLevelRewards, useShopProducts } from "./tuning";

const MILESTONES = [2, 5, 10, 20, 30];

function threshold(base: number, exponent: number, level: number): number {
  return level <= 1 ? 0 : Math.round(base * (level - 1) ** exponent);
}

/**
 * Levels (027): the curve (XP needed for each level, previewed live) and the level tiers — what reaching a
 * level gives (Coins, Contribution, a shop product offered) next to what it unlocks in the shop (products
 * whose minimum level is in the tier).
 */
export function LevelsPanel({ detailed = true }: { detailed?: boolean }) {
  const t = useT();
  const format = useFormat();
  const curve = useLevelCurve();
  const publish = usePublishCurve();
  const { query, save } = useLevelRewards();
  const products = useShopProducts();
  const [base, setBase] = useState(100);
  const [exponent, setExponent] = useState(1.5);
  const [tiers, setTiers] = useState<LevelReward[]>([]);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (curve.data) {
      setBase(curve.data.definition.base);
      setExponent(curve.data.definition.exponent);
    }
  }, [curve.data]);
  useEffect(() => {
    if (query.data) setTiers(query.data.rewards);
  }, [query.data]);
  const top = Math.max(30, ...tiers.map((tier) => tier.level));
  const points = Array.from({ length: top }, (_, i) => ({
    level: i + 1,
    xp: threshold(base, exponent, i + 1),
  }));
  const sorted = [...tiers].sort((a, b) => a.level - b.level);
  const shop = (products.data ?? []).filter((p) => p.state !== "archived");
  const unlocked = (low: number, high: number): ShopProduct[] =>
    shop.filter((p) => p.min_level && p.min_level > low && p.min_level <= high);
  const changedCurve =
    !!curve.data && (curve.data.definition.base !== base || curve.data.definition.exponent !== exponent);
  const patch = (index: number, next: Partial<LevelReward>) => {
    setSaved(false);
    setTiers(tiers.map((tier, i) => (i === index ? { ...tier, ...next } : tier)));
  };
  return (
    <>
      {detailed ? (
        <AdminSection
          span="full"
          icon="chart"
          title={t("gamification:admin.curve")}
          description={t("gamification:admin.curve.hint")}
        >
          <div className="gam-curve">
            <div className="gam-curve__form">
              <TextField
                label={t("gamification:admin.curve.base")}
                hint={t("gamification:admin.curve.baseHint")}
                type="number"
                min={1}
                value={String(base)}
                onChange={(e) => setBase(Number(e.target.value))}
              />
              <TextField
                label={t("gamification:admin.curve.exponent")}
                hint={t("gamification:admin.curve.exponentHint")}
                type="number"
                step="0.05"
                min={1}
                max={3}
                value={String(exponent)}
                onChange={(e) => setExponent(Number(e.target.value))}
              />
              <dl className="gam-milestones">
                {MILESTONES.map((level) => (
                  <div key={level}>
                    <dt>{t("gamification:level", { level })}</dt>
                    <dd>
                      {format.number(threshold(base, exponent, level))} {t("gamification:value.xp")}
                    </dd>
                  </div>
                ))}
              </dl>
              <FormActions>
                <Button
                  disabled={!changedCurve || publish.isPending}
                  onClick={() => publish.mutate({ kind: "power", base, exponent })}
                >
                  <Icon name="check" size={16} />
                  {t("gamification:admin.curve.save")}
                </Button>
              </FormActions>
            </div>
            <figure className="gam-chart">
              <figcaption>{t("gamification:admin.curve.chart")}</figcaption>
              <div aria-hidden="true">
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={points}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="level" stroke="var(--color-text-muted)" fontSize={12} />
                    <YAxis stroke="var(--color-text-muted)" fontSize={12} width={56} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="xp"
                      stroke="var(--color-accent)"
                      strokeWidth={2}
                      dot={false}
                    />
                    {sorted.map((tier) => (
                      <ReferenceDot
                        key={tier.level}
                        x={tier.level}
                        y={threshold(base, exponent, tier.level)}
                        r={5}
                        fill="var(--color-accent-alt)"
                        stroke="var(--color-surface)"
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </figure>
          </div>
        </AdminSection>
      ) : null}
      <AdminSection
        span="full"
        icon="gift"
        title={t("gamification:admin.levels.title")}
        description={t("gamification:admin.levels.hint")}
        actions={
          <Button
            variant="secondary"
            onClick={() => {
              setSaved(false);
              const last = sorted.at(-1)?.level ?? 0;
              setTiers([
                ...sorted,
                { level: last ? last + 5 : 5, xp: 0, coins: 0, contribution: 0, product: null, label: "" },
              ]);
            }}
          >
            <Icon name="plus" size={16} />
            {t("gamification:admin.levels.add")}
          </Button>
        }
      >
        {!sorted.length ? <p className="admin-muted">{t("gamification:admin.levels.empty")}</p> : null}
        <ol className="gam-tiers">
          {tiers.map((tier, index) => {
            const previous = Math.max(0, ...tiers.filter((x) => x.level < tier.level).map((x) => x.level));
            const opens = unlocked(previous, tier.level);
            return (
              // biome-ignore lint/suspicious/noArrayIndexKey: a tier's level is being edited, the row stays
              <li key={index} className="gam-level">
                <div className="gam-level__badge" aria-hidden="true">
                  <span>{tier.level}</span>
                </div>
                <div className="gam-level__body">
                  <div className="gam-level__head">
                    <strong>{tier.label || t("gamification:level", { level: tier.level })}</strong>
                    <span className="admin-muted">
                      {t("gamification:admin.levels.from", {
                        xp: format.number(threshold(base, exponent, tier.level)),
                      })}
                    </span>
                  </div>
                  <div className="gam-level__fields">
                    <TextField
                      label={t("gamification:admin.levels.level")}
                      type="number"
                      min={2}
                      max={1000}
                      value={String(tier.level)}
                      onChange={(e) => patch(index, { level: Number(e.target.value) })}
                    />
                    <TextField
                      label={t("gamification:admin.levels.label")}
                      maxLength={120}
                      value={tier.label ?? ""}
                      placeholder={t("gamification:admin.levels.labelExample")}
                      onChange={(e) => patch(index, { label: e.target.value })}
                    />
                    <TextField
                      label="XP"
                      type="number"
                      min={0}
                      value={String(tier.xp ?? 0)}
                      onChange={(e) => patch(index, { xp: Number(e.target.value) })}
                    />
                    <TextField
                      label={t("gamification:value.coins")}
                      type="number"
                      min={0}
                      value={String(tier.coins ?? 0)}
                      onChange={(e) => patch(index, { coins: Number(e.target.value) })}
                    />
                    <TextField
                      label={t("gamification:value.contribution")}
                      type="number"
                      min={0}
                      value={String(tier.contribution ?? 0)}
                      onChange={(e) => patch(index, { contribution: Number(e.target.value) })}
                    />
                    <SelectField
                      label={t("gamification:admin.levels.product")}
                      value={tier.product ?? ""}
                      onChange={(e) => patch(index, { product: e.target.value || null })}
                    >
                      <option value="">{t("gamification:admin.levels.noProduct")}</option>
                      {shop.map((p) => (
                        <option key={p.key} value={p.key}>
                          {p.name}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <div className="gam-level__unlocks">
                    <span className="admin-muted">
                      <Icon name="lock" size={12} /> {t("gamification:admin.levels.unlocks")}
                    </span>
                    {opens.length ? (
                      opens.map((p) => (
                        <span key={p.key} className="gam-chip" data-kind="shop">
                          {p.name} · {t("gamification:level", { level: p.min_level ?? 0 })}
                        </span>
                      ))
                    ) : (
                      <span className="admin-muted">{t("gamification:admin.levels.noUnlock")}</span>
                    )}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("gamification:admin.remove")}
                  onClick={() => {
                    setSaved(false);
                    setTiers(tiers.filter((_, i) => i !== index));
                  }}
                >
                  <Icon name="trash" size={16} />
                </Button>
              </li>
            );
          })}
        </ol>
        {save.isError ? (
          <p role="alert" className="services-admin__ko">
            {t("gamification:admin.saveFailed")}
          </p>
        ) : null}
        {saved ? <p role="status">{t("gamification:admin.saved")}</p> : null}
        <FormActions>
          <Link className="ds-button ds-button--ghost" to="/admin/marketplace">
            <Icon name="shop" size={16} />
            {t("gamification:admin.levels.shop")}
          </Link>
          <Button
            disabled={save.isPending}
            onClick={() => save.mutate(sorted, { onSuccess: () => setSaved(true) })}
          >
            <Icon name="check" size={16} />
            {t("gamification:admin.save")}
          </Button>
        </FormActions>
      </AdminSection>
    </>
  );
}
