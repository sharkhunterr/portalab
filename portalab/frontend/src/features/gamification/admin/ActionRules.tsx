import { type FormEvent, useState } from "react";
import {
  AdminEmpty,
  AdminSection,
  FormActions,
  FormGrid,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { type Translate, useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { GameRuleBuilder, gameRuleChips, useProposedGameRules } from "../../games/RewardRules";
import { type RewardRule, useRuleAdmin, useRules, type Value } from "../api";
import { SimulationPanel } from "./SimulationPanel";
import { OPS, PLAY_KINDS, parseValue, playName } from "./StepFilters";
import {
  actionLabel,
  type Condition,
  type EventTypeInfo,
  keyOf,
  PER_MINUTE_FIELDS,
  type RuleDefinition,
  type RuleGrant,
  useEventTypes,
  VALUES,
} from "./tuning";

const OWNER_ICONS: Record<string, string> = {
  media: "play",
  marketplace: "shop",
  support: "lifebuoy",
  community: "users",
  wiki: "book",
  news: "newspaper",
  calendar: "calendar",
  campaigns: "flame",
  games: "dices", // issue 265: the games page
};

export function ownerIcon(eventType: string): string {
  const head = eventType.split(".")[0] ?? "";
  if (head === "ticket" || head === "feedback" || head === "incident") return "lifebuoy";
  if (head === "project") return "lightbulb"; // issue 314: the community projects
  return OWNER_ICONS[head] ?? "zap";
}

/** Ready-made rules for the actions every portal rewards (027). */
function presets(t: Translate): Array<{ key: string; icon: string; definition: RuleDefinition }> {
  return [
    {
      key: "media.playback",
      icon: "play",
      definition: {
        event_type: "media.playback_finished",
        label: t("gamification:admin.presets.playback"),
        grants: [
          { value: "xp", amount: 10, per_unit: { field: "duration_s", factor: 1 / 60, max: 180 } },
          { value: "coins", amount: 2 },
        ],
        limits: { caps: [{ period: "day", max_amount: 600, value: "xp" }] },
      },
    },
    // issue 234: a content's booster — a film watched to the end, a season finished
    {
      key: "cards.film",
      icon: "gift",
      definition: {
        event_type: "media.playback_finished",
        label: t("gamification:admin.presets.filmBooster"),
        predicate: [{ field: "kind", op: "in", value: ["movie"] }],
        grants: [],
        boosters: 1,
      },
    },
    {
      key: "cards.season",
      icon: "gift",
      definition: {
        event_type: "media.season_finished",
        label: t("gamification:admin.presets.seasonBooster"),
        grants: [],
        boosters: 1,
      },
    },
    // issue 351: a game played (RomM) — its time only: XP a minute, a few coins an hour of a session; and a big
    // reward once a game was played as long as its main story takes
    {
      key: "media.game_time",
      icon: "gamepad",
      definition: {
        event_type: "media.playback_abandoned",
        label: t("gamification:admin.presets.gameTime"),
        predicate: [{ field: "kind", op: "in", value: ["game"] }],
        grants: [
          { value: "xp", per_unit: { field: "watched_s", factor: 1 / 60, max: 240 } },
          { value: "coins", per_unit: { field: "watched_s", factor: 5 / 3600, max: 20 } },
        ],
        limits: { caps: [{ period: "day", max_amount: 300, value: "xp" }] },
      },
    },
    {
      key: "media.game_length",
      icon: "trophy",
      definition: {
        event_type: "media.game_length_reached",
        label: t("gamification:admin.presets.gameLength"),
        grants: [
          { value: "xp", amount: 200 },
          { value: "coins", amount: 100 },
        ],
      },
    },
    {
      key: "marketplace.purchase",
      icon: "shop",
      definition: {
        event_type: "marketplace.purchase",
        label: t("gamification:admin.presets.purchase"),
        grants: [{ value: "xp", amount: 15 }],
      },
    },
    {
      key: "support.ticket",
      icon: "lifebuoy",
      definition: {
        event_type: "ticket.created",
        label: t("gamification:admin.presets.ticket"),
        grants: [
          { value: "xp", amount: 10 },
          { value: "contribution", amount: 2 },
        ],
        limits: { cooldown_seconds: 600, caps: [{ period: "day", max_amount: 50, value: "xp" }] },
      },
    },
    // issue 355: a title reviewed (rated, a few words if wanted) — once per title, a few a day
    {
      key: "media.review",
      icon: "star",
      definition: {
        event_type: "media.reviewed",
        label: t("gamification:admin.presets.review"),
        grants: [
          { value: "xp", amount: 5 },
          { value: "coins", amount: 2 },
        ],
        limits: { caps: [{ period: "day", max_amount: 25, value: "xp" }] },
      },
    },
    // issue 354: a problem reported on a media's page, once the team resolved it (a real one, then)
    {
      key: "support.media_report",
      icon: "flag",
      definition: {
        event_type: "ticket.resolved",
        label: t("gamification:admin.presets.mediaReport"),
        predicate: [{ field: "media", op: "eq", value: true }],
        grants: [
          { value: "xp", amount: 25 },
          { value: "coins", amount: 15 },
          { value: "contribution", amount: 3 },
        ],
        limits: { caps: [{ period: "day", max_amount: 75, value: "xp" }] },
      },
    },
  ];
}

/** « 10 XP + 1 XP/min (max 180) » — what one grant gives, in words. */
export function grantText(t: Translate, grant: RuleGrant): string {
  const unit = t(`gamification:value.${grant.value}`);
  const parts: string[] = [];
  if (grant.amount) parts.push(`${grant.amount} ${unit}`);
  if (grant.per_unit) {
    const minutes = PER_MINUTE_FIELDS.has(grant.per_unit.field);
    const rate = Math.round(grant.per_unit.factor * (minutes ? 60 : 1) * 100) / 100;
    const per = minutes
      ? t("gamification:admin.rule.perMinute", { rate, unit })
      : t("gamification:admin.rule.perUnit", { rate, unit, field: grant.per_unit.field });
    parts.push(
      grant.per_unit.max ? `${per} (${t("gamification:admin.rule.max", { max: grant.per_unit.max })})` : per,
    );
  }
  return parts.join(" + ");
}

interface GrantRow {
  amount: string;
  field: string;
  rate: string;
  max: string;
}

function toRows(grants: RuleGrant[]): Record<Value, GrantRow> {
  const rows = {} as Record<Value, GrantRow>;
  for (const value of VALUES) {
    const grant = grants.find((g) => g.value === value);
    const minutes = grant?.per_unit ? PER_MINUTE_FIELDS.has(grant.per_unit.field) : false;
    rows[value] = {
      amount: grant?.amount ? String(grant.amount) : "",
      field: grant?.per_unit?.field ?? "",
      rate: grant?.per_unit
        ? String(Math.round(grant.per_unit.factor * (minutes ? 60 : 1) * 1000) / 1000)
        : "",
      max: grant?.per_unit?.max ? String(grant.per_unit.max) : "",
    };
  }
  return rows;
}

function fromRows(rows: Record<Value, GrantRow>): RuleGrant[] {
  const out: RuleGrant[] = [];
  for (const value of VALUES) {
    const row = rows[value];
    const amount = Number(row.amount) || 0;
    const rate = Number(row.rate) || 0;
    const grant: RuleGrant = { value };
    if (amount > 0) grant.amount = Math.round(amount);
    if (row.field && rate > 0) {
      const factor = PER_MINUTE_FIELDS.has(row.field) ? rate / 60 : rate;
      grant.per_unit = {
        field: row.field,
        factor,
        ...(Number(row.max) > 0 ? { max: Math.round(Number(row.max)) } : {}),
      };
    }
    if (grant.amount || grant.per_unit) out.push(grant);
  }
  return out;
}

function RuleForm({
  ruleKey,
  initial,
  types,
  onDone,
}: {
  ruleKey?: string;
  initial: RuleDefinition;
  types: EventTypeInfo[];
  onDone: () => void;
}) {
  const t = useT();
  const admin = useRuleAdmin();
  const [key, setKey] = useState(ruleKey ?? keyOf(initial.label ?? ""));
  const [label, setLabel] = useState(initial.label ?? "");
  const [eventType, setEventType] = useState(initial.event_type);
  const [rows, setRows] = useState(() => toRows(initial.grants));
  const [conditions, setConditions] = useState<Array<{ field: string; op: Condition["op"]; value: string }>>(
    () =>
      (initial.predicate ?? []).map((c) => ({
        field: c.field,
        op: c.op,
        value: Array.isArray(c.value) ? c.value.join(", ") : String(c.value),
      })),
  );
  const [cooldown, setCooldown] = useState(String(Math.round((initial.limits?.cooldown_seconds ?? 0) / 60)));
  const firstCap = initial.limits?.caps?.[0];
  const [capPeriod, setCapPeriod] = useState(firstCap?.period ?? "day");
  const [capAmount, setCapAmount] = useState(firstCap ? String(firstCap.max_amount) : "");
  const [capValue, setCapValue] = useState<Value>(firstCap?.value ?? "xp");
  const [multiplier, setMultiplier] = useState(String(initial.multiplier ?? 1));
  const [boosters, setBoosters] = useState(String(initial.boosters ?? 0));
  const [error, setError] = useState<string | null>(null);
  const info = types.find((type) => type.name === eventType);
  const fields = info?.fields ?? [];
  const numericFields = fields.filter((f) => f.numeric);
  // issue 160: the playback actions pick their kinds of play as chips (a « kind » condition underneath)
  const aboutContent = eventType.startsWith("media.");
  const playKinds = eventType.startsWith("media.playback_") && fields.some((f) => f.name === "kind");
  const kindIndex = conditions.findIndex((c) => c.field === "kind" && (c.op === "in" || c.op === "eq"));
  const chosenKinds =
    kindIndex < 0
      ? []
      : (conditions[kindIndex]?.value ?? "")
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean);
  const toggleKind = (raw: string) => {
    const next = chosenKinds.includes(raw) ? chosenKinds.filter((k) => k !== raw) : [...chosenKinds, raw];
    const rest = conditions.filter((_, i) => i !== kindIndex);
    setConditions(next.length ? [...rest, { field: "kind", op: "in", value: next.join(", ") }] : rest);
  };
  const definition: RuleDefinition = {
    event_type: eventType,
    label,
    grants: fromRows(rows),
    ...(Number(boosters) > 0 ? { boosters: Math.min(3, Math.round(Number(boosters))) } : {}),
    predicate: conditions
      .filter((c) => c.field && c.value !== "")
      .map((c) => ({
        field: c.field,
        op: c.op,
        value: parseValue(c.value, fields.find((f) => f.name === c.field)?.numeric ?? false, c.op),
      })),
    multiplier: Number(multiplier) || 1,
    limits: {
      cooldown_seconds: Math.max(0, Math.round(Number(cooldown) || 0)) * 60,
      caps:
        Number(capAmount) > 0
          ? [{ period: capPeriod, max_amount: Math.round(Number(capAmount)), value: capValue }]
          : [],
      ...(initial.limits?.diminishing ? { diminishing: initial.limits.diminishing } : {}),
    },
  };
  const owners = [...new Set(types.map((type) => type.owner))].sort();
  const submit = async (publish: boolean) => {
    setError(null);
    try {
      const saved = await admin.save.mutateAsync({
        key,
        definition: definition as unknown as Record<string, unknown>,
      });
      if (publish && saved) await admin.publish.mutateAsync({ key, version: saved.version });
      onDone();
    } catch (failure) {
      const errors =
        failure instanceof ApiError ? (failure.extensions.errors as string[] | undefined) : undefined;
      setError(
        failure instanceof ApiError
          ? [failure.message, ...(errors ?? [])].join(" — ")
          : t("gamification:admin.rule.invalid"),
      );
    }
  };
  const setRow = (value: Value, patch: Partial<GrantRow>) =>
    setRows({ ...rows, [value]: { ...rows[value], ...patch } });
  return (
    <form
      className="admin-form gam-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        void submit(true);
      }}
    >
      <FormGrid>
        <TextField
          label={t("gamification:admin.rule.label")}
          required
          maxLength={120}
          value={label}
          onChange={(e) => {
            setLabel(e.target.value);
            if (!ruleKey) setKey(keyOf(e.target.value));
          }}
        />
        <SelectField
          label={t("gamification:admin.rule.action")}
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
        >
          {owners.map((owner) => (
            <optgroup key={owner} label={owner.replace(/^module:/, "")}>
              {types
                .filter((type) => type.owner === owner)
                .map((type) => (
                  <option key={type.name} value={type.name}>
                    {actionLabel(t, type.name)}
                  </option>
                ))}
            </optgroup>
          ))}
        </SelectField>
        {!ruleKey ? (
          <TextField
            label={t("gamification:admin.rule.key")}
            hint={t("gamification:admin.rule.keyHint")}
            required
            pattern="^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        ) : null}
      </FormGrid>

      <fieldset className="gam-fieldset">
        <legend>{t("gamification:admin.rule.gains")}</legend>
        <p className="admin-muted">{t("gamification:admin.rule.gainsHint")}</p>
        <div className="gam-grants">
          {VALUES.map((value) => {
            const row = rows[value];
            const minutes = PER_MINUTE_FIELDS.has(row.field);
            return (
              <div key={value} className="gam-grant" data-value={value}>
                <strong className="gam-grant__value">{t(`gamification:value.${value}`)}</strong>
                <TextField
                  label={t("gamification:admin.rule.fixed")}
                  type="number"
                  min={0}
                  inputMode="numeric"
                  value={row.amount}
                  onChange={(e) => setRow(value, { amount: e.target.value })}
                />
                {numericFields.length ? (
                  <>
                    <SelectField
                      label={t("gamification:admin.rule.plusPer")}
                      value={row.field}
                      onChange={(e) => setRow(value, { field: e.target.value })}
                    >
                      <option value="">{t("gamification:admin.rule.nothing")}</option>
                      {numericFields.map((f) => (
                        <option key={f.name} value={f.name}>
                          {PER_MINUTE_FIELDS.has(f.name)
                            ? t("gamification:admin.rule.minuteOf", { field: f.name })
                            : f.name}
                        </option>
                      ))}
                    </SelectField>
                    <TextField
                      label={
                        minutes
                          ? t("gamification:admin.rule.ratePerMinute")
                          : t("gamification:admin.rule.rate")
                      }
                      type="number"
                      min={0}
                      step="any"
                      disabled={!row.field}
                      value={row.rate}
                      onChange={(e) => setRow(value, { rate: e.target.value })}
                    />
                    <TextField
                      label={t("gamification:admin.rule.maxPart")}
                      type="number"
                      min={0}
                      disabled={!row.field}
                      value={row.max}
                      onChange={(e) => setRow(value, { max: e.target.value })}
                    />
                  </>
                ) : null}
              </div>
            );
          })}
        </div>
        {aboutContent ? (
          // issue 234: the content's own boosters (its work's cards), once per member and content
          <TextField
            label={t("gamification:admin.rule.boosters")}
            hint={t("gamification:admin.rule.boostersHint")}
            type="number"
            min={0}
            max={3}
            inputMode="numeric"
            value={boosters}
            onChange={(e) => setBoosters(e.target.value)}
          />
        ) : null}
      </fieldset>

      {playKinds ? (
        <fieldset className="gam-fieldset">
          <legend>{t("gamification:admin.rule.playKinds")}</legend>
          <p className="admin-muted">{t("gamification:admin.rule.playKindsHint")}</p>
          <div className="gam-kinds">
            {PLAY_KINDS.map(([raw]) => (
              <button
                key={raw}
                type="button"
                className="gam-kinds__chip"
                aria-pressed={chosenKinds.includes(raw)}
                onClick={() => toggleKind(raw)}
              >
                {playName(t, raw)}
              </button>
            ))}
          </div>
        </fieldset>
      ) : null}

      {fields.length ? (
        <fieldset className="gam-fieldset">
          <legend>{t("gamification:admin.rule.conditions")}</legend>
          {conditions.map((condition, index) =>
            playKinds && index === kindIndex ? null : (
              // biome-ignore lint/suspicious/noArrayIndexKey: rows have no identity of their own
              <div key={index} className="gam-condition">
                <SelectField
                  label={t("gamification:admin.rule.field")}
                  value={condition.field}
                  onChange={(e) =>
                    setConditions(
                      conditions.map((c, i) => (i === index ? { ...c, field: e.target.value } : c)),
                    )
                  }
                >
                  {fields.map((f) => (
                    <option key={f.name} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </SelectField>
                <SelectField
                  label={t("gamification:admin.rule.op")}
                  value={condition.op}
                  onChange={(e) =>
                    setConditions(
                      conditions.map((c, i) =>
                        i === index ? { ...c, op: e.target.value as Condition["op"] } : c,
                      ),
                    )
                  }
                >
                  {OPS.map((op) => (
                    <option key={op} value={op}>
                      {t(`gamification:admin.op.${op}`)}
                    </option>
                  ))}
                </SelectField>
                <TextField
                  label={t("gamification:admin.rule.value")}
                  value={condition.value}
                  onChange={(e) =>
                    setConditions(
                      conditions.map((c, i) => (i === index ? { ...c, value: e.target.value } : c)),
                    )
                  }
                />
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("gamification:admin.remove")}
                  onClick={() => setConditions(conditions.filter((_, i) => i !== index))}
                >
                  <Icon name="trash" size={16} />
                </Button>
              </div>
            ),
          )}
          <Button
            variant="secondary"
            onClick={() =>
              setConditions([...conditions, { field: fields[0]?.name ?? "", op: "eq", value: "" }])
            }
          >
            <Icon name="plus" size={16} />
            {t("gamification:admin.rule.addCondition")}
          </Button>
        </fieldset>
      ) : null}

      <fieldset className="gam-fieldset">
        <legend>{t("gamification:admin.rule.limits")}</legend>
        <FormGrid>
          <TextField
            label={t("gamification:admin.rule.cooldown")}
            hint={t("gamification:admin.rule.cooldownHint")}
            type="number"
            min={0}
            value={cooldown}
            onChange={(e) => setCooldown(e.target.value)}
          />
          <TextField
            label={t("gamification:admin.rule.cap")}
            hint={t("gamification:admin.rule.capHint")}
            type="number"
            min={0}
            value={capAmount}
            onChange={(e) => setCapAmount(e.target.value)}
          />
          <SelectField
            label={t("gamification:admin.rule.capValue")}
            value={capValue}
            onChange={(e) => setCapValue(e.target.value as Value)}
          >
            {VALUES.map((v) => (
              <option key={v} value={v}>
                {t(`gamification:value.${v}`)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label={t("gamification:admin.rule.capPeriod")}
            value={capPeriod}
            onChange={(e) => setCapPeriod(e.target.value as "hour" | "day" | "week")}
          >
            {(["hour", "day", "week"] as const).map((p) => (
              <option key={p} value={p}>
                {t(`gamification:admin.period.${p}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("gamification:admin.rule.multiplier")}
            type="number"
            min={0.1}
            max={100}
            step="0.1"
            value={multiplier}
            onChange={(e) => setMultiplier(e.target.value)}
          />
        </FormGrid>
      </fieldset>

      <details className="gam-advanced">
        <summary>{t("gamification:admin.rule.advanced")}</summary>
        <pre>{JSON.stringify(definition, null, 2)}</pre>
        <SimulationPanel ruleKey={key} definition={definition as unknown as Record<string, unknown>} />
      </details>

      {error ? (
        <p role="alert" className="services-admin__ko">
          {error}
        </p>
      ) : null}
      <FormActions>
        <Button
          variant="secondary"
          disabled={!key || admin.save.isPending}
          onClick={() => void submit(false)}
        >
          {t("gamification:admin.rule.saveDraft")}
        </Button>
        <Button
          type="submit"
          disabled={!key || (!definition.grants.length && !definition.boosters) || admin.save.isPending}
        >
          <Icon name="check" size={16} />
          {t("gamification:admin.rule.savePublish")}
        </Button>
      </FormActions>
    </form>
  );
}

const TONES: Record<string, "ok" | "info" | "neutral"> = { active: "ok", draft: "info", retired: "neutral" };

function RuleCard({
  rule,
  types,
  open,
  setOpen,
}: {
  rule: RewardRule;
  types: EventTypeInfo[];
  open: string | null;
  setOpen: (key: string | null) => void;
}) {
  const t = useT();
  const format = useFormat();
  const admin = useRuleAdmin();
  const definition = rule.definition as unknown as RuleDefinition;
  const caps = definition.limits?.caps ?? [];
  return (
    <li className="gam-rule" data-status={rule.status}>
      <span className="gam-rule__icon" aria-hidden="true">
        <Icon name={ownerIcon(rule.event_type)} size={20} />
      </span>
      <div className="gam-rule__text">
        <strong>{definition.label || actionLabel(t, rule.event_type)}</strong>
        <span className="admin-muted">
          {actionLabel(t, rule.event_type)} · {rule.key} · v{rule.version}
        </span>
        <span className="gam-chips">
          {definition.grants.map((grant) => (
            <span key={grant.value} className="gam-chip" data-value={grant.value}>
              {grantText(t, grant)}
            </span>
          ))}
          {definition.boosters ? (
            <span className="gam-chip" data-value="booster">
              <Icon name="gift" size={12} />{" "}
              {t("gamification:admin.rule.boostersChip", { count: definition.boosters })}
            </span>
          ) : null}
          {/* issue 265: a game's rule says its conditions in words (the game, the score, the place…) */}
          {rule.event_type.startsWith("games.")
            ? gameRuleChips(t, rule.event_type, definition.predicate ?? []).map((chip) => (
                <span key={chip} className="gam-chip" data-kind="if">
                  <Icon name="dices" size={12} /> {chip}
                </span>
              ))
            : null}
          {(rule.event_type.startsWith("games.") ? [] : (definition.predicate ?? [])).map((c) =>
            c.field === "kind" && (c.op === "in" || c.op === "eq") ? (
              <span key={`${c.field}${c.op}`} className="gam-chip" data-kind="if">
                <Icon name="play" size={12} />{" "}
                {(Array.isArray(c.value) ? c.value : [c.value]).map((v) => playName(t, String(v))).join(", ")}
              </span>
            ) : (
              <span key={`${c.field}${c.op}`} className="gam-chip" data-kind="if">
                {c.field} {t(`gamification:admin.op.${c.op}`)}{" "}
                {Array.isArray(c.value) ? c.value.join(", ") : String(c.value)}
              </span>
            ),
          )}
          {definition.limits?.cooldown_seconds ? (
            <span className="gam-chip" data-kind="limit">
              <Icon name="clock" size={12} />{" "}
              {t("gamification:admin.rule.cooldownChip", {
                minutes: Math.round(definition.limits.cooldown_seconds / 60),
              })}
            </span>
          ) : null}
          {caps.map((cap) => (
            <span key={`${cap.period}${cap.value}`} className="gam-chip" data-kind="limit">
              {t("gamification:admin.rule.capChip", {
                amount: format.number(cap.max_amount),
                unit: t(`gamification:value.${cap.value ?? "xp"}`),
                period: t(`gamification:admin.period.${cap.period}`),
              })}
            </span>
          ))}
        </span>
      </div>
      <span className="gam-rule__actions">
        <StatusBadge tone={TONES[rule.status] ?? "neutral"}>
          {t(`gamification:admin.status.${rule.status}`)}
        </StatusBadge>
        {rule.status === "draft" ? (
          <Button
            variant="secondary"
            onClick={() => admin.publish.mutate({ key: rule.key, version: rule.version })}
          >
            {t("gamification:admin.rule.publish", { version: rule.version })}
          </Button>
        ) : null}
        <Dialog
          open={open === rule.key}
          onOpenChange={(next) => setOpen(next ? rule.key : null)}
          title={definition.label || rule.key}
          closeLabel={t("gamification:admin.close")}
          size="lg"
          trigger={
            <Button variant="ghost" aria-label={t("gamification:admin.edit")}>
              <Icon name="settings" size={16} />
            </Button>
          }
        >
          <RuleForm ruleKey={rule.key} initial={definition} types={types} onDone={() => setOpen(null)} />
        </Dialog>
        {rule.status === "active" ? (
          <Button
            variant="ghost"
            aria-label={t("gamification:admin.rule.retire")}
            onClick={() => {
              if (window.confirm(t("gamification:admin.rule.retireConfirm"))) admin.retire.mutate(rule.key);
            }}
          >
            <Icon name="trash" size={16} />
          </Button>
        ) : null}
      </span>
    </li>
  );
}

/**
 * XP per action (027): each rule says what one action gives — a fixed amount, an amount per minute
 * watched (or per unit of any measured attribute), or both — with optional conditions and limits.
 * Saving publishes a new version (older versions stay in the history, never edited).
 */
export function ActionRules() {
  const t = useT();
  const rules = useRules();
  const types = useEventTypes();
  const [open, setOpen] = useState<string | null>(null);
  const [preset, setPreset] = useState<RuleDefinition | null>(null);
  const games = useProposedGameRules(); // issue 265: the games' rules live here, with every other
  const list = (rules.data ?? []).filter((rule) => rule.status !== "retired");
  const retired = (rules.data ?? []).filter((rule) => rule.status === "retired");
  const typeList = types.data ?? [];
  // a preset is offered while no rule does its part (issue 234: a booster preset, while no rule of its action
  // gives boosters)
  const available = presets(t).filter(
    (p) =>
      !list.some(
        (rule) =>
          rule.event_type === p.definition.event_type &&
          Boolean((rule.definition as unknown as RuleDefinition).boosters) === Boolean(p.definition.boosters),
      ),
  );
  const blank: RuleDefinition = {
    event_type: typeList[0]?.name ?? "media.playback_finished",
    label: "",
    grants: [],
  };
  return (
    <AdminSection
      span="full"
      icon="zap"
      title={t("gamification:admin.rules")}
      description={t("gamification:admin.rules.hint")}
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => {
            setOpen(next ? "new" : null);
            if (!next) setPreset(null);
          }}
          title={t("gamification:admin.rule.new")}
          closeLabel={t("gamification:admin.close")}
          size="lg"
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("gamification:admin.rule.new")}
            </Button>
          }
        >
          <RuleForm
            initial={preset ?? blank}
            types={typeList}
            onDone={() => setOpen(null)}
            key={preset ? `${preset.event_type}:${preset.boosters ?? 0}` : "blank"}
          />
        </Dialog>
      }
    >
      <div className="gam-presets" id="games-rules">
        <span className="admin-muted">{t("gamification:admin.presets.title")}</span>
        {available.map((p) => (
          <Button
            key={p.key}
            variant="secondary"
            onClick={() => {
              setPreset(p.definition);
              setOpen("new");
            }}
          >
            <Icon name={p.icon} size={16} />
            {p.definition.label}
          </Button>
        ))}
        {/* issue 265: a mini-game's rule in a few choices (taking part, a score, a win, a place, a challenge) */}
        <Dialog
          open={open === "games"}
          onOpenChange={(next) => setOpen(next ? "games" : null)}
          title={t("gamification:admin.presets.game")}
          closeLabel={t("gamification:admin.close")}
          size="lg"
          trigger={
            <Button variant="secondary">
              <Icon name="dices" size={16} />
              {t("gamification:admin.presets.game")}
            </Button>
          }
        >
          <GameRuleBuilder
            taken={new Set((rules.data ?? []).map((rule) => rule.key))}
            onDone={() => setOpen(null)}
          />
        </Dialog>
        {games.missing ? (
          <Button variant="secondary" disabled={games.create.isPending} onClick={() => games.create.mutate()}>
            <Icon name="sparkles" size={16} />
            {t("gamification:admin.presets.games")}
          </Button>
        ) : null}
      </div>
      {games.create.error ? (
        <p role="alert" className="services-admin__ko">
          {games.create.error.message}
        </p>
      ) : null}
      {rules.data && !list.length ? (
        <AdminEmpty icon="zap" title={t("gamification:admin.rules.empty")} />
      ) : (
        <ul className="gam-rules">
          {list.map((rule) => (
            <RuleCard key={rule.key} rule={rule} types={typeList} open={open} setOpen={setOpen} />
          ))}
        </ul>
      )}
      {retired.length ? (
        <details className="gam-advanced">
          <summary>{t("gamification:admin.rules.retired", { count: retired.length })}</summary>
          <ul className="gam-rules">
            {retired.map((rule) => (
              <RuleCard key={rule.key} rule={rule} types={typeList} open={open} setOpen={setOpen} />
            ))}
          </ul>
        </details>
      ) : null}
    </AdminSection>
  );
}
