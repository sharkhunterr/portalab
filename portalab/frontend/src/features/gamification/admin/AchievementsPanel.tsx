import { type FormEvent, useState } from "react";
import {
  AdminEmpty,
  AdminSection,
  AdminTabs,
  FormActions,
  FormGrid,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { type Translate, useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import type { Value } from "../api";
import {
  type AchievementDefinition,
  actionLabel,
  type Criterion,
  type EventCount,
  type EventTypeInfo,
  keyOf,
  type QuestDefinition,
  type Reward,
  UNLOCK_KINDS,
  type Unlock,
  useAchievementAdmin,
  useEventTypes,
  useQuestAdmin,
  useShopProducts,
  VALUES,
  type Versioned,
} from "./tuning";

const CATEGORIES = ["service_usage", "purchase", "community", "progression", "events", "content", "other"];
const ICONS = [
  "trophy",
  "medal",
  "award",
  "star",
  "crown",
  "gem",
  "flame",
  "film",
  "tv",
  "book",
  "shop",
  "heart",
  "rocket",
  "target",
];
const KINDS: Criterion["kind"][] = ["event_count", "level_at_least", "value_at_least", "statistic_at_least"];

export function criterionText(t: Translate, criterion: Criterion): string {
  switch (criterion.kind) {
    case "event_count":
      return t("gamification:admin.criterion.eventCountText", {
        count: criterion.count,
        action: actionLabel(t, criterion.event_type),
      });
    case "level_at_least":
      return t("gamification:admin.criterion.levelText", { level: criterion.level });
    case "value_at_least":
      return t("gamification:admin.criterion.valueText", {
        amount: criterion.amount,
        unit: t(`gamification:value.${criterion.value}`),
      });
    default:
      return t("gamification:admin.criterion.statisticText", {
        statistic: criterion.statistic,
        amount: criterion.amount,
      });
  }
}

function blankCriterion(kind: Criterion["kind"], types: EventTypeInfo[]): Criterion {
  switch (kind) {
    case "event_count":
      return { kind, event_type: types[0]?.name ?? "media.playback_finished", count: 10 };
    case "level_at_least":
      return { kind, level: 5 };
    case "value_at_least":
      return { kind, value: "xp", amount: 1000 };
    default:
      return { kind: "statistic_at_least", statistic: "media.hours_watched", amount: 10 };
  }
}

function ActionSelect({
  value,
  types,
  onChange,
}: {
  value: string;
  types: EventTypeInfo[];
  onChange: (value: string) => void;
}) {
  const t = useT();
  return (
    <SelectField
      label={t("gamification:admin.rule.action")}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {types.map((type) => (
        <option key={type.name} value={type.name}>
          {actionLabel(t, type.name)}
        </option>
      ))}
    </SelectField>
  );
}

function CriterionEditor({
  criterion,
  types,
  onChange,
  onRemove,
  stepsOnly = false,
}: {
  criterion: Criterion;
  types: EventTypeInfo[];
  onChange: (next: Criterion) => void;
  onRemove: () => void;
  stepsOnly?: boolean;
}) {
  const t = useT();
  return (
    <div className="gam-criterion">
      {!stepsOnly ? (
        <SelectField
          label={t("gamification:admin.criterion.kind")}
          value={criterion.kind}
          onChange={(e) => onChange(blankCriterion(e.target.value as Criterion["kind"], types))}
        >
          {KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {t(`gamification:admin.criterion.${kind}`)}
            </option>
          ))}
        </SelectField>
      ) : null}
      {criterion.kind === "event_count" ? (
        <>
          <ActionSelect
            value={criterion.event_type}
            types={types}
            onChange={(v) => onChange({ ...criterion, event_type: v })}
          />
          <TextField
            label={t("gamification:admin.criterion.count")}
            type="number"
            min={1}
            value={String(criterion.count)}
            onChange={(e) => onChange({ ...criterion, count: Number(e.target.value) })}
          />
        </>
      ) : null}
      {criterion.kind === "level_at_least" ? (
        <TextField
          label={t("gamification:admin.levels.level")}
          type="number"
          min={1}
          value={String(criterion.level)}
          onChange={(e) => onChange({ ...criterion, level: Number(e.target.value) })}
        />
      ) : null}
      {criterion.kind === "value_at_least" ? (
        <>
          <SelectField
            label={t("gamification:admin.grant.value")}
            value={criterion.value}
            onChange={(e) => onChange({ ...criterion, value: e.target.value as Value })}
          >
            {VALUES.map((v) => (
              <option key={v} value={v}>
                {t(`gamification:value.${v}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("gamification:admin.grant.amount")}
            type="number"
            min={1}
            value={String(criterion.amount)}
            onChange={(e) => onChange({ ...criterion, amount: Number(e.target.value) })}
          />
        </>
      ) : null}
      {criterion.kind === "statistic_at_least" ? (
        <>
          <TextField
            label={t("gamification:admin.criterion.statistic")}
            value={criterion.statistic}
            onChange={(e) => onChange({ ...criterion, statistic: e.target.value })}
          />
          <TextField
            label={t("gamification:admin.grant.amount")}
            type="number"
            min={0}
            step="any"
            value={String(criterion.amount)}
            onChange={(e) => onChange({ ...criterion, amount: Number(e.target.value) })}
          />
        </>
      ) : null}
      <Button variant="ghost" size="icon" aria-label={t("gamification:admin.remove")} onClick={onRemove}>
        <Icon name="trash" size={16} />
      </Button>
    </div>
  );
}

function RewardsEditor({ rewards, onChange }: { rewards: Reward[]; onChange: (next: Reward[]) => void }) {
  const t = useT();
  return (
    <fieldset className="gam-fieldset">
      <legend>{t("gamification:admin.rewards")}</legend>
      <div className="gam-grants gam-grants--compact">
        {VALUES.map((value) => {
          const amount = rewards.find((r) => r.value === value)?.amount ?? 0;
          return (
            <TextField
              key={value}
              label={t(`gamification:value.${value}`)}
              type="number"
              min={0}
              value={String(amount)}
              onChange={(e) => {
                const next = rewards.filter((r) => r.value !== value);
                const n = Math.round(Number(e.target.value) || 0);
                onChange(n > 0 ? [...next, { value, amount: n }] : next);
              }}
            />
          );
        })}
      </div>
    </fieldset>
  );
}

/** #81: the shop products an achievement gives — a look, or a sealed booster opened from the reserve. */
function UnlocksEditor({ unlocks, onChange }: { unlocks: Unlock[]; onChange: (next: Unlock[]) => void }) {
  const t = useT();
  const products = useShopProducts();
  const choices = (products.data ?? []).filter(
    (p) => p.state !== "archived" && (UNLOCK_KINDS as readonly string[]).includes(p.type),
  );
  return (
    <fieldset className="gam-fieldset">
      <legend>{t("gamification:admin.unlocks")}</legend>
      <p className="admin-muted">{t("gamification:admin.unlocksHint")}</p>
      {unlocks.map((unlock, index) => (
        <div key={unlock.product} className="gam-unlock">
          <span className="gam-chip" data-kind="shop">
            {unlock.label}
          </span>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("gamification:admin.remove")}
            onClick={() => onChange(unlocks.filter((_, i) => i !== index))}
          >
            <Icon name="trash" size={16} />
          </Button>
        </div>
      ))}
      {unlocks.length < 4 ? (
        <SelectField
          label={t("gamification:admin.unlockAdd")}
          value=""
          onChange={(e) => {
            const product = choices.find((p) => p.key === e.target.value);
            if (product && !unlocks.some((u) => u.product === product.key)) {
              onChange([
                ...unlocks,
                { product: product.key, kind: product.type, label: product.name.slice(0, 80) },
              ]);
            }
          }}
        >
          <option value="">{t("gamification:admin.unlockNone")}</option>
          {choices.map((p) => (
            <option key={p.key} value={p.key}>
              {p.name}
            </option>
          ))}
        </SelectField>
      ) : null}
    </fieldset>
  );
}

function useSubmitError() {
  const t = useT();
  const [error, setError] = useState<string | null>(null);
  const fail = (failure: unknown) => {
    const errors =
      failure instanceof ApiError ? (failure.extensions.errors as string[] | undefined) : undefined;
    setError(
      failure instanceof ApiError
        ? [failure.message, ...(errors ?? [])].join(" — ")
        : t("gamification:admin.saveFailed"),
    );
  };
  return { error, setError, fail };
}

function AchievementForm({
  item,
  preset,
  types,
  onDone,
}: {
  item?: Versioned<AchievementDefinition>;
  preset?: { key: string; definition: AchievementDefinition } | null;
  types: EventTypeInfo[];
  onDone: () => void;
}) {
  const t = useT();
  const { save } = useAchievementAdmin();
  const { error, setError, fail } = useSubmitError();
  const [key, setKey] = useState(item?.key ?? preset?.key ?? "");
  const [def, setDef] = useState<AchievementDefinition>(
    item?.definition ??
      preset?.definition ?? {
        label: "",
        description: "",
        icon: "trophy",
        category: "service_usage",
        hidden: false,
        criteria: [blankCriterion("event_count", types)],
        rewards: [{ value: "xp", amount: 50 }],
      },
  );
  const patch = (next: Partial<AchievementDefinition>) => setDef({ ...def, ...next });
  return (
    <form
      className="admin-form gam-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        setError(null);
        save.mutate({ key, definition: def }, { onSuccess: onDone, onError: fail });
      }}
    >
      <FormGrid>
        <TextField
          label={t("gamification:admin.rule.label")}
          required
          maxLength={120}
          value={def.label}
          onChange={(e) => {
            patch({ label: e.target.value });
            if (!item) setKey(keyOf(e.target.value));
          }}
        />
        <SelectField
          label={t("gamification:admin.icon")}
          value={def.icon ?? "trophy"}
          onChange={(e) => patch({ icon: e.target.value })}
        >
          {ICONS.map((icon) => (
            <option key={icon} value={icon}>
              {icon}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("gamification:admin.category")}
          value={def.category ?? "other"}
          onChange={(e) => patch({ category: e.target.value })}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`gamification:achievements.category.${c}`)}
            </option>
          ))}
        </SelectField>
        {!item ? (
          <TextField
            label={t("gamification:admin.rule.key")}
            required
            pattern="^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        ) : null}
      </FormGrid>
      <TextField
        label={t("gamification:admin.description_field")}
        maxLength={400}
        value={def.description ?? ""}
        onChange={(e) => patch({ description: e.target.value })}
      />
      <CheckboxField
        label={t("gamification:admin.achievement.hidden")}
        hint={t("gamification:admin.achievement.hiddenHint")}
        checked={def.hidden ?? false}
        onChange={(e) => patch({ hidden: e.target.checked })}
      />
      <fieldset className="gam-fieldset">
        <legend>{t("gamification:admin.criteria")}</legend>
        <p className="admin-muted">{t("gamification:admin.criteria.hint")}</p>
        {def.criteria.map((criterion, index) => (
          <CriterionEditor
            // biome-ignore lint/suspicious/noArrayIndexKey: criteria have no identity of their own
            key={index}
            criterion={criterion}
            types={types}
            onChange={(next) => patch({ criteria: def.criteria.map((c, i) => (i === index ? next : c)) })}
            onRemove={() => patch({ criteria: def.criteria.filter((_, i) => i !== index) })}
          />
        ))}
        {def.criteria.length < 5 ? (
          <Button
            variant="secondary"
            onClick={() => patch({ criteria: [...def.criteria, blankCriterion("event_count", types)] })}
          >
            <Icon name="plus" size={16} />
            {t("gamification:admin.criteria.add")}
          </Button>
        ) : null}
      </fieldset>
      <RewardsEditor rewards={def.rewards ?? []} onChange={(rewards) => patch({ rewards })} />
      <UnlocksEditor unlocks={def.unlocks ?? []} onChange={(unlocks) => patch({ unlocks })} />
      {error ? (
        <p role="alert" className="services-admin__ko">
          {error}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={!key || !def.criteria.length || save.isPending}>
          <Icon name="check" size={16} />
          {t("gamification:admin.save")}
        </Button>
      </FormActions>
    </form>
  );
}

function QuestForm({
  item,
  types,
  onDone,
}: {
  item?: Versioned<QuestDefinition>;
  types: EventTypeInfo[];
  onDone: () => void;
}) {
  const t = useT();
  const { save } = useQuestAdmin();
  const { error, setError, fail } = useSubmitError();
  const [key, setKey] = useState(item?.key ?? "");
  const [def, setDef] = useState<QuestDefinition>(
    item?.definition ?? {
      kind: "daily",
      label: "",
      description: "",
      icon: "target",
      period: "day",
      steps: [blankCriterion("event_count", types) as EventCount],
      rewards: [{ value: "xp", amount: 30 }],
    },
  );
  const patch = (next: Partial<QuestDefinition>) => setDef({ ...def, ...next });
  const local = (iso?: string) => (iso ? iso.slice(0, 16) : "");
  return (
    <form
      className="admin-form gam-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        setError(null);
        const span = def.window?.starts_at && def.window.ends_at ? def.window : null;
        // issue 307: texts rewritten here are the ones every member reads — no older translation over them
        const rewritten =
          item && (def.label !== item.definition.label || def.description !== item.definition.description);
        const definition = { ...def, window: span, ...(rewritten ? { translations: {} } : {}) };
        save.mutate({ key, definition }, { onSuccess: onDone, onError: fail });
      }}
    >
      <FormGrid>
        <TextField
          label={t("gamification:admin.rule.label")}
          required
          maxLength={120}
          value={def.label}
          onChange={(e) => {
            patch({ label: e.target.value });
            if (!item) setKey(keyOf(e.target.value));
          }}
        />
        <SelectField
          label={t("gamification:admin.quest.kind")}
          value={def.kind}
          onChange={(e) => {
            const kind = e.target.value as QuestDefinition["kind"];
            patch({ kind, period: kind === "daily" ? "day" : kind === "challenge" ? "none" : def.period });
          }}
        >
          {(["daily", "quest", "challenge"] as const).map((kind) => (
            <option key={kind} value={kind}>
              {t(`gamification:admin.quest.kinds.${kind}`)}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("gamification:admin.quest.period")}
          value={def.period ?? "none"}
          onChange={(e) => patch({ period: e.target.value as QuestDefinition["period"] })}
        >
          {(["none", "day", "week", "month"] as const).map((p) => (
            <option key={p} value={p}>
              {t(`gamification:admin.quest.periods.${p}`)}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("gamification:admin.icon")}
          value={def.icon ?? "target"}
          onChange={(e) => patch({ icon: e.target.value })}
        >
          {ICONS.map((icon) => (
            <option key={icon} value={icon}>
              {icon}
            </option>
          ))}
        </SelectField>
        {!item ? (
          <TextField
            label={t("gamification:admin.rule.key")}
            required
            pattern="^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        ) : null}
      </FormGrid>
      <TextField
        label={t("gamification:admin.description_field")}
        maxLength={400}
        value={def.description ?? ""}
        onChange={(e) => patch({ description: e.target.value })}
      />
      <FormGrid>
        <TextField
          label={t("gamification:admin.quest.starts")}
          hint={def.kind === "challenge" ? undefined : t("gamification:admin.quest.windowHint")}
          type="datetime-local"
          required={def.kind === "challenge"}
          value={local(def.window?.starts_at)}
          onChange={(e) =>
            patch({
              window: {
                starts_at: new Date(e.target.value).toISOString(),
                ends_at: def.window?.ends_at ?? "",
              },
            })
          }
        />
        <TextField
          label={t("gamification:admin.quest.ends")}
          type="datetime-local"
          required={def.kind === "challenge"}
          value={local(def.window?.ends_at)}
          onChange={(e) =>
            patch({
              window: {
                starts_at: def.window?.starts_at ?? "",
                ends_at: new Date(e.target.value).toISOString(),
              },
            })
          }
        />
      </FormGrid>
      <fieldset className="gam-fieldset">
        <legend>{t("gamification:admin.quest.steps")}</legend>
        {def.steps.map((step, index) => (
          <CriterionEditor
            // biome-ignore lint/suspicious/noArrayIndexKey: steps have no identity of their own
            key={index}
            stepsOnly
            criterion={step}
            types={types}
            onChange={(next) =>
              patch({ steps: def.steps.map((s, i) => (i === index ? (next as EventCount) : s)) })
            }
            onRemove={() => patch({ steps: def.steps.filter((_, i) => i !== index) })}
          />
        ))}
        {def.steps.length < 5 ? (
          <Button
            variant="secondary"
            onClick={() =>
              patch({ steps: [...def.steps, blankCriterion("event_count", types) as EventCount] })
            }
          >
            <Icon name="plus" size={16} />
            {t("gamification:admin.quest.addStep")}
          </Button>
        ) : null}
        {def.steps.length > 1 ? (
          <SelectField
            label={t("gamification:admin.quest.completeOn")}
            value={def.complete_on ?? "all"}
            onChange={(e) => patch({ complete_on: e.target.value as "all" | "any" })}
          >
            {(["all", "any"] as const).map((mode) => (
              <option key={mode} value={mode}>
                {t(`gamification:admin.quest.completeOnModes.${mode}`)}
              </option>
            ))}
          </SelectField>
        ) : null}
      </fieldset>
      <RewardsEditor rewards={def.rewards ?? []} onChange={(rewards) => patch({ rewards })} />
      {error ? (
        <p role="alert" className="services-admin__ko">
          {error}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={!key || !def.steps.length || save.isPending}>
          <Icon name="check" size={16} />
          {t("gamification:admin.save")}
        </Button>
      </FormActions>
    </form>
  );
}

function rewardsText(t: Translate, rewards: Reward[] | undefined): string {
  return (rewards ?? []).map((r) => `+${r.amount} ${t(`gamification:value.${r.value}`)}`).join(" · ");
}

/** Issue 234: ready-made achievements of the card collections — boosters opened, a legendary, collections
 * completed (films, series). */
function presets(t: Translate): Array<{ key: string; definition: AchievementDefinition }> {
  const make = (
    key: string,
    icon: string,
    event: string,
    count: number,
    xp: number,
    filter: EventCount["filter"] = [],
  ) => ({
    key,
    definition: {
      label: t(`gamification:admin.cardAchievements.${key}.label`),
      description: t(`gamification:admin.cardAchievements.${key}.description`),
      icon,
      category: "content",
      hidden: false,
      criteria: [{ kind: "event_count" as const, event_type: event, filter, count }],
      rewards: [{ value: "xp" as const, amount: xp }],
    },
  });
  return [
    make("cards_first_booster", "gift", "cards.pack_opened", 1, 25),
    make("cards_boosters_25", "layers", "cards.pack_opened", 25, 150),
    make("cards_legendary", "crown", "cards.pack_opened", 1, 100, [
      { field: "legendary", op: "gte", value: 1 },
    ]),
    make("cards_first_collection", "trophy", "cards.set_completed", 1, 150),
    make("cards_series_collections", "tv", "cards.set_completed", 3, 250, [
      { field: "kind", op: "eq", value: "series" },
    ]),
    make("cards_collections_10", "library", "cards.set_completed", 10, 500),
  ];
}

/** Achievements (027): one card per achievement — icon, category, criteria in words, rewards — edited in a form. */
export function AchievementsPanel() {
  const t = useT();
  const { query, retire } = useAchievementAdmin();
  const types = useEventTypes();
  const [open, setOpen] = useState<string | null>(null);
  const [preset, setPreset] = useState<{ key: string; definition: AchievementDefinition } | null>(null);
  const [category, setCategory] = useState("all");
  const items = (query.data ?? []).filter((a) => category === "all" || a.definition.category === category);
  const typeList = types.data ?? [];
  const present = [...new Set((query.data ?? []).map((a) => a.definition.category ?? "other"))];
  const available = presets(t).filter((p) => !(query.data ?? []).some((a) => a.key === p.key));
  return (
    <AdminSection
      span="full"
      icon="trophy"
      title={t("gamification:admin.tabs.achievements")}
      description={t("gamification:admin.achievements.hint")}
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => {
            setOpen(next ? "new" : null);
            if (!next) setPreset(null);
          }}
          title={t("gamification:admin.achievement.new")}
          closeLabel={t("gamification:admin.close")}
          size="lg"
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("gamification:admin.achievement.new")}
            </Button>
          }
        >
          <AchievementForm
            key={preset?.key ?? "blank"}
            preset={preset}
            types={typeList}
            onDone={() => setOpen(null)}
          />
        </Dialog>
      }
    >
      {available.length && typeList.some((type) => type.name === "cards.pack_opened") ? (
        <div className="gam-presets">
          <span className="admin-muted">{t("gamification:admin.cardAchievements.title")}</span>
          {available.map((p) => (
            <Button
              key={p.key}
              variant="secondary"
              onClick={() => {
                setPreset(p);
                setOpen("new");
              }}
            >
              <Icon name={p.definition.icon ?? "trophy"} size={16} />
              {p.definition.label}
            </Button>
          ))}
        </div>
      ) : null}
      {present.length > 1 ? (
        <AdminTabs
          label={t("gamification:admin.category")}
          current={category}
          onChange={setCategory}
          tabs={[
            { key: "all", label: t("gamification:admin.all"), count: query.data?.length ?? 0 },
            ...CATEGORIES.filter((c) => present.includes(c)).map((c) => ({
              key: c,
              label: t(`gamification:achievements.category.${c}`),
              count: (query.data ?? []).filter((a) => (a.definition.category ?? "other") === c).length,
            })),
          ]}
        />
      ) : null}
      {query.data && !query.data.length ? (
        <AdminEmpty icon="trophy" title={t("gamification:admin.achievements.empty")} />
      ) : null}
      <ul className="gam-cards">
        {items.map((item) => (
          <li key={item.key} className="gam-card">
            <span className="gam-card__icon" aria-hidden="true">
              <Icon name={item.definition.icon ?? "trophy"} size={22} />
            </span>
            <div className="gam-card__body">
              <strong>{item.definition.label}</strong>
              {item.definition.description ? (
                <span className="admin-muted">{item.definition.description}</span>
              ) : null}
              <span className="gam-chips">
                {item.definition.criteria.map((c, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: criteria have no identity of their own
                  <span key={i} className="gam-chip" data-kind="if">
                    {criterionText(t, c)}
                  </span>
                ))}
                {item.definition.rewards?.length ? (
                  <span className="gam-chip" data-value="xp">
                    {rewardsText(t, item.definition.rewards)}
                  </span>
                ) : null}
              </span>
            </div>
            <span className="gam-card__actions">
              {item.definition.hidden ? (
                <StatusBadge tone="info">{t("gamification:admin.achievement.hidden")}</StatusBadge>
              ) : null}
              {item.source !== "own" ? (
                <StatusBadge tone="neutral">{t("gamification:admin.fromCampaign")}</StatusBadge>
              ) : (
                <>
                  <Dialog
                    open={open === item.key}
                    onOpenChange={(next) => setOpen(next ? item.key : null)}
                    title={item.definition.label}
                    closeLabel={t("gamification:admin.close")}
                    size="lg"
                    trigger={
                      <Button variant="ghost" aria-label={t("gamification:admin.edit")}>
                        <Icon name="settings" size={16} />
                      </Button>
                    }
                  >
                    <AchievementForm item={item} types={typeList} onDone={() => setOpen(null)} />
                  </Dialog>
                  <Button
                    variant="ghost"
                    aria-label={t("gamification:admin.rule.retire")}
                    onClick={() => {
                      if (window.confirm(t("gamification:admin.rule.retireConfirm"))) retire.mutate(item.key);
                    }}
                  >
                    <Icon name="trash" size={16} />
                  </Button>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}

/** Quests, daily objectives and time-boxed challenges (027): steps in words, rewards, period. */
export function QuestsPanel() {
  const t = useT();
  const format = useFormat();
  const { query, retire } = useQuestAdmin();
  const types = useEventTypes();
  const [open, setOpen] = useState<string | null>(null);
  const typeList = types.data ?? [];
  return (
    <AdminSection
      span="full"
      icon="target"
      title={t("gamification:admin.tabs.quests")}
      description={t("gamification:admin.quests.hint")}
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => setOpen(next ? "new" : null)}
          title={t("gamification:admin.quest.new")}
          closeLabel={t("gamification:admin.close")}
          size="lg"
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("gamification:admin.quest.new")}
            </Button>
          }
        >
          <QuestForm types={typeList} onDone={() => setOpen(null)} />
        </Dialog>
      }
    >
      {query.data && !query.data.length ? (
        <AdminEmpty icon="target" title={t("gamification:admin.quests.empty")} />
      ) : null}
      <ul className="gam-cards">
        {(query.data ?? []).map((item) => (
          <li key={item.key} className="gam-card">
            <span className="gam-card__icon" aria-hidden="true">
              <Icon name={item.definition.icon ?? "target"} size={22} />
            </span>
            <div className="gam-card__body">
              <strong>{item.definition.label}</strong>
              <span className="admin-muted">
                {t(`gamification:admin.quest.kinds.${item.definition.kind}`)} ·{" "}
                {t(`gamification:admin.quest.periods.${item.definition.period ?? "none"}`)}
                {item.definition.window
                  ? ` · ${t("gamification:admin.quest.window", {
                      from: format.date(item.definition.window.starts_at, "medium"),
                      to: format.date(item.definition.window.ends_at, "medium"),
                    })}`
                  : ""}
              </span>
              <span className="gam-chips">
                {item.definition.steps.map((s, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: steps have no identity of their own
                  <span key={i} className="gam-chip" data-kind="if">
                    {criterionText(t, s)}
                  </span>
                ))}
                {item.definition.rewards?.length ? (
                  <span className="gam-chip" data-value="xp">
                    {rewardsText(t, item.definition.rewards)}
                  </span>
                ) : null}
              </span>
            </div>
            <span className="gam-card__actions">
              {item.source !== "own" ? (
                <StatusBadge tone="neutral">{t("gamification:admin.fromCampaign")}</StatusBadge>
              ) : (
                <>
                  <Dialog
                    open={open === item.key}
                    onOpenChange={(next) => setOpen(next ? item.key : null)}
                    title={item.definition.label}
                    closeLabel={t("gamification:admin.close")}
                    size="lg"
                    trigger={
                      <Button variant="ghost" aria-label={t("gamification:admin.edit")}>
                        <Icon name="settings" size={16} />
                      </Button>
                    }
                  >
                    <QuestForm item={item} types={typeList} onDone={() => setOpen(null)} />
                  </Dialog>
                  <Button
                    variant="ghost"
                    aria-label={t("gamification:admin.rule.retire")}
                    onClick={() => {
                      if (window.confirm(t("gamification:admin.rule.retireConfirm"))) retire.mutate(item.key);
                    }}
                  >
                    <Icon name="trash" size={16} />
                  </Button>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}
