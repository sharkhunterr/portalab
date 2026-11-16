import { type FormEvent, useId, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { Dialog, DialogActions } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { ApiError } from "../../state/regions";
import { Switch } from "../account/SettingsKit";
import { useCatalogFacets } from "../media/api";
import {
  AGES,
  FEATURES,
  GENRES,
  type HouseholdMember,
  type ProfileKind,
  type RestrictionSettings,
  TYPES,
  useCreateProfile,
  useDeleteProfile,
  useHousehold,
  useRatingPolicy,
  useSetPin,
  useUpdateProfile,
} from "./api";
import { ProfileFace } from "./ProfilePicker";
import { ScreenPlanner } from "./ScreenPlanner";
import { ScreenScope } from "./ScreenScope";

const KINDS: ProfileKind[] = ["standard", "child", "custom"];
const PRESETS: Record<ProfileKind, { restrictions: RestrictionSettings; community: boolean }> = {
  standard: {
    restrictions: {
      max_age: null,
      allow_unrated: true,
      blocked: [],
      mode: "hide",
      requests: true,
      services: true,
      screen_scope: "media",
      rating_blend: "strictest",
    },
    community: true,
  },
  child: {
    restrictions: {
      max_age: 12,
      allow_unrated: false,
      blocked: ["ai", "community", "requests", "shop"],
      mode: "hide",
      requests: true,
      genres: ["crime", "horror", "thriller", "war"], // issue 432: at least these for a child
      services: false,
      screen_scope: "media",
      rating_blend: "strictest",
    },
    community: false,
  },
  custom: {
    restrictions: {
      max_age: null,
      allow_unrated: true,
      blocked: [],
      mode: "hide",
      requests: true,
      services: true,
      screen_scope: "media",
      rating_blend: "strictest",
    },
    community: true,
  },
};
const KIND_ICONS: Record<ProfileKind, string> = { standard: "user", child: "smile", custom: "sliders" };
const MODES = ["show", "hide", "lock"] as const;
const MODE_ICONS: Record<(typeof MODES)[number], string> = { show: "eye", hide: "hide", lock: "lock" };

/** A genre as the portal keeps it out: its words, lowercased (the server knows the four usual ones). */
export function genreKey(value: string): string {
  return (value.toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []).join(" ").slice(0, 60);
}

/** A list with ``key`` in it or not. */
function flip(list: readonly string[] | undefined, key: string, on: boolean): string[] {
  const rest = (list ?? []).filter((item) => item !== key);
  return on ? [...rest, key].sort() : rest;
}

/** Its age today, from its birth date (« 2016-03-10 »). */
export function ageOf(birth: string | null | undefined, today = new Date()): number | null {
  if (!birth) return null;
  const [year, month, day] = birth.split("-").map(Number) as [number, number, number];
  const before = today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day);
  return today.getFullYear() - year - (before ? 1 : 0);
}

/** Creating a profile, or (the master) setting one: its name, colour, kind, restrictions, PIN, community. */
export function ProfileEditor({
  member,
  position,
  palette,
  economy = "pot",
  onClose,
}: {
  member: HouseholdMember | null;
  position: number;
  palette: readonly string[];
  economy?: string;
  onClose: () => void;
}) {
  const t = useT();
  const notify = useNotify();
  const formId = useId();
  const create = useCreateProfile();
  const update = useUpdateProfile();
  const remove = useDeleteProfile();
  const setPin = useSetPin();
  const editing = member !== null;
  const startKind = (member?.kind === "owner" ? "standard" : member?.kind) ?? "standard";
  const [name, setName] = useState(member?.display_name ?? "");
  const [kind, setKind] = useState<ProfileKind>(startKind);
  const [color, setColor] = useState(member?.color ?? palette[position % palette.length] ?? palette[0] ?? "");
  const [restrictions, setRestrictions] = useState<RestrictionSettings>(
    member?.restrictions ?? PRESETS[startKind].restrictions,
  );
  const [community, setCommunity] = useState(member?.community_visible ?? PRESETS[startKind].community);
  const [pin, setPinValue] = useState("");
  const [confirming, setConfirming] = useState(false);
  const pending = create.isPending || update.isPending || setPin.isPending || remove.isPending;
  const failed = [create.error, update.error, setPin.error, remove.error].find(Boolean);
  const pinInvalid = pin !== "" && !/^\d{4,6}$/.test(pin);

  const chooseKind = (next: ProfileKind) => {
    setKind(next);
    setRestrictions(PRESETS[next].restrictions);
    setCommunity(PRESETS[next].community);
  };
  const toggle = (feature: string, on: boolean) =>
    setRestrictions((r) => ({
      ...r,
      blocked: on ? [...(r.blocked ?? []), feature].sort() : (r.blocked ?? []).filter((f) => f !== feature),
    }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (pinInvalid || !name.trim()) return;
    try {
      if (editing) {
        await update.mutateAsync({
          id: member.id,
          display_name: name.trim(),
          color,
          kind,
          restrictions,
          community_visible: community,
        });
        if (pin) await setPin.mutateAsync({ id: member.id, pin });
        notify({ severity: "success", title: t("household:editor.saved") });
      } else {
        const created = await create.mutateAsync({
          display_name: name.trim(),
          kind,
          color,
          ...(pin ? { pin } : {}),
        });
        const preset = PRESETS[kind];
        if (
          JSON.stringify(preset.restrictions) !== JSON.stringify(restrictions) ||
          preset.community !== community
        )
          await update.mutateAsync({ id: created.id, restrictions, community_visible: community });
        notify({ severity: "success", title: t("household:editor.created") });
      }
      onClose();
    } catch {
      // the error is shown below
    }
  };

  const title = editing ? t("household:page.edit", { name: member.display_name }) : t("household:editor.new");
  return (
    <Dialog
      trigger={null}
      open
      size="lg"
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={title}
      closeLabel={t("household:editor.cancel")}
    >
      <form id={formId} className="household-editor" onSubmit={submit}>
        <div className="household-editor__identity">
          <ProfileFace
            member={{
              id: member?.id ?? "new",
              display_name: name || "?",
              color,
              has_avatar: Boolean(member?.has_avatar),
            }}
          />
          <div className="household-editor__fields">
            <TextField
              label={t("household:editor.name")}
              value={name}
              maxLength={64}
              required
              onChange={(event) => setName(event.target.value)}
            />
            <fieldset className="household-editor__colors">
              <legend>{t("household:editor.color")}</legend>
              {palette.map((swatch) => (
                <label key={swatch} style={{ "--swatch": swatch } as React.CSSProperties}>
                  <input
                    type="radio"
                    name={`${formId}-color`}
                    value={swatch}
                    checked={color === swatch}
                    onChange={() => setColor(swatch)}
                    aria-label={t("household:editor.colorOption", { color: swatch })}
                  />
                </label>
              ))}
            </fieldset>
          </div>
        </div>

        <fieldset className="household-editor__kinds">
          <legend>{t("household:editor.kind")}</legend>
          <p className="household-editor__hint">{t("household:editor.kindHint")}</p>
          {KINDS.map((option) => (
            <label key={option} data-checked={kind === option || undefined}>
              <input
                type="radio"
                name={`${formId}-kind`}
                value={option}
                checked={kind === option}
                onChange={() => chooseKind(option)}
              />
              <Icon name={KIND_ICONS[option]} size={20} />
              <span>{t(`household:kind.${option}`)}</span>
            </label>
          ))}
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.ageSection")}</legend>
          <AgeLimitField
            name={`${formId}-limit`}
            restrictions={restrictions}
            onChange={(change) => setRestrictions((r) => ({ ...r, ...change }))}
          />
          <fieldset className="household-editor__modes">
            <legend className="household-editor__label">{t("household:editor.mode")}</legend>
            {MODES.map((mode) => (
              <label key={mode} data-checked={restrictions.mode === mode || undefined}>
                <input
                  type="radio"
                  name={`${formId}-mode`}
                  value={mode}
                  checked={restrictions.mode === mode}
                  onChange={() => setRestrictions((r) => ({ ...r, mode }))}
                />
                <Icon name={MODE_ICONS[mode]} size={18} />
                <span>
                  <strong>{t(`household:editor.mode_${mode}`)}</strong>
                  <small>{t(`household:editor.mode_${mode}Hint`)}</small>
                </span>
              </label>
            ))}
          </fieldset>
          <div className="household-switches">
            <Switch
              label={t("household:editor.unrated")}
              checked={restrictions.allow_unrated ?? true}
              onChange={(event) => setRestrictions((r) => ({ ...r, allow_unrated: event.target.checked }))}
            />
            <Switch
              label={t("household:editor.requests")}
              checked={restrictions.requests ?? true}
              onChange={(event) => setRestrictions((r) => ({ ...r, requests: event.target.checked }))}
            />
          </div>
        </fieldset>

        <ClassificationField
          name={`${formId}-read`}
          restrictions={restrictions}
          onChange={(change) => setRestrictions((r) => ({ ...r, ...change }))}
        />

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.types")}</legend>
          <p className="household-editor__hint">{t("household:editor.typesHint")}</p>
          <div className="household-switches">
            {TYPES.map((kind) => (
              <Switch
                key={kind}
                label={t(`household:type.${kind}`)}
                checked={!(restrictions.types ?? []).includes(kind)}
                onChange={(event) =>
                  setRestrictions((r) => ({ ...r, types: flip(r.types, kind, !event.target.checked) }))
                }
              />
            ))}
          </div>
        </fieldset>

        <GenresField
          genres={restrictions.genres ?? []}
          onChange={(genres) => setRestrictions((r) => ({ ...r, genres }))}
        />

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.titles")}</legend>
          {(restrictions.titles ?? []).length === 0 ? (
            <p className="household-editor__hint">{t("household:editor.titlesEmpty")}</p>
          ) : (
            <ul className="household-kept">
              {(restrictions.titles ?? []).map((title) => (
                <li key={title.id}>
                  <Icon name="blocked" size={16} />
                  <span>{title.title || title.id}</span>
                  <Button
                    variant="ghost"
                    type="button"
                    onClick={() =>
                      setRestrictions((r) => ({
                        ...r,
                        titles: (r.titles ?? []).filter((k) => k.id !== title.id),
                      }))
                    }
                  >
                    {t("household:editor.titlesRemove")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.features")}</legend>
          <Switch
            label={t("household:editor.services")}
            checked={restrictions.services ?? true}
            onChange={(event) => setRestrictions((r) => ({ ...r, services: event.target.checked }))}
          />
          <p className="household-editor__hint">{t("household:editor.servicesHint")}</p>
          <div className="household-switches">
            {FEATURES.map((feature) => (
              <Switch
                key={feature}
                label={t(`household:feature.${feature}`)}
                checked={!(restrictions.blocked ?? []).includes(feature)}
                onChange={(event) => toggle(feature, !event.target.checked)}
              />
            ))}
          </div>
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.screen")}</legend>
          <ScreenScope
            name={`${formId}-scope`}
            value={restrictions.screen_scope}
            onChange={(screen_scope) => setRestrictions((r) => ({ ...r, screen_scope }))}
          />
          <ScreenPlanner
            plan={restrictions}
            onChange={(plan) => setRestrictions((r) => ({ ...r, ...plan }))}
          />
          <p className="household-editor__hint">{t("household:editor.screenHint")}</p>
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.community")}</legend>
          {economy === "pot" ? (
            // issue 443: a common pot — the master stands for the household, its profiles stay private
            <p className="household-editor__hint">{t("household:editor.communityPot")}</p>
          ) : (
            <>
              <Switch
                label={t("household:editor.communityPublic")}
                checked={community}
                onChange={(event) => setCommunity(event.target.checked)}
              />
              <p className="household-editor__hint">
                {t(
                  community
                    ? "household:editor.communityPublicHint"
                    : "household:editor.communityAnonymousHint",
                )}
              </p>
            </>
          )}
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.pin")}</legend>
          <TextField
            label={t("household:editor.pin")}
            hint={t("household:editor.pinHint")}
            type="password"
            inputMode="numeric"
            autoComplete="new-password"
            maxLength={6}
            value={pin}
            error={pinInvalid ? t("household:pin.hint") : undefined}
            onChange={(event) => setPinValue(event.target.value.replace(/\D/g, ""))}
          />
          {editing && member.has_pin ? (
            <Button
              variant="ghost"
              type="button"
              disabled={pending}
              onClick={() =>
                setPin.mutate(
                  { id: member.id, pin: null },
                  { onSuccess: () => notify({ severity: "success", title: t("household:myPin.saved") }) },
                )
              }
            >
              <Icon name="lock" size={16} />
              {t("household:editor.removePin")}
            </Button>
          ) : null}
        </fieldset>

        {editing ? (
          <div className="household-editor__danger">
            {confirming ? (
              <>
                <p role="alert">{t("household:editor.deleteConfirm", { name: member.display_name })}</p>
                <Button variant="ghost" type="button" onClick={() => setConfirming(false)}>
                  {t("household:editor.cancel")}
                </Button>
                <Button
                  variant="danger"
                  type="button"
                  disabled={pending}
                  onClick={() =>
                    remove.mutate(member.id, {
                      onSuccess: () => {
                        notify({ severity: "success", title: t("household:editor.deleted") });
                        onClose();
                      },
                    })
                  }
                >
                  <Icon name="trash" size={16} />
                  {t("household:editor.delete")}
                </Button>
              </>
            ) : (
              <Button variant="ghost" type="button" onClick={() => setConfirming(true)}>
                <Icon name="trash" size={16} />
                {t("household:editor.delete")}
              </Button>
            )}
          </div>
        ) : null}

        {failed ? (
          <p role="alert" className="household-error">
            {failed instanceof ApiError && failed.code === "household.limit"
              ? failed.message
              : t("household:error")}
          </p>
        ) : null}
        <DialogActions>
          <Button type="submit" disabled={pending || pinInvalid || !name.trim()}>
            <Icon name="check" size={16} />
            {editing ? t("household:editor.save") : t("household:editor.create")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** Issue 432: the genres kept out — the usual four as switches, any other genre of the catalog by name. */
function GenresField({ genres, onChange }: { genres: string[]; onChange: (genres: string[]) => void }) {
  const t = useT();
  const listId = useId();
  const [typed, setTyped] = useState("");
  const facets = useCatalogFacets(undefined);
  const known = new Set<string>(GENRES);
  const others = genres.filter((genre) => !known.has(genre));
  const offered = [...new Set((facets.data?.genres ?? []).map((genre) => genre.trim()).filter(Boolean))]
    .filter((genre) => !genres.includes(genreKey(genre)))
    .sort((a, b) => a.localeCompare(b));
  const add = () => {
    const key = genreKey(typed);
    if (key && !genres.includes(key)) onChange([...genres, key].sort());
    setTyped("");
  };
  return (
    <fieldset className="household-editor__section">
      <legend>{t("household:editor.genres")}</legend>
      <p className="household-editor__hint">{t("household:editor.genresHint")}</p>
      <div className="household-switches">
        {GENRES.map((genre) => (
          <Switch
            key={genre}
            label={t(`household:genre.${genre}`)}
            checked={genres.includes(genre)}
            onChange={(event) => onChange(flip(genres, genre, event.target.checked))}
          />
        ))}
      </div>
      {others.length ? (
        <ul className="household-genres" aria-label={t("household:editor.genresOther")}>
          {others.map((genre) => (
            <li key={genre}>
              <span>{genre}</span>
              <button
                type="button"
                aria-label={t("household:editor.genresRemove", { genre })}
                onClick={() => onChange(genres.filter((g) => g !== genre))}
              >
                <Icon name="close" size={14} />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="household-genres__add">
        <TextField
          label={t("household:editor.genresAdd")}
          hint={t("household:editor.genresAddHint")}
          value={typed}
          maxLength={60}
          list={listId}
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
        />
        <datalist id={listId}>
          {offered.map((genre) => (
            <option key={genre} value={genre} />
          ))}
        </datalist>
        <Button variant="secondary" type="button" disabled={!genreKey(typed)} onClick={add}>
          <Icon name="plus" size={16} />
          {t("household:editor.genresAddButton")}
        </Button>
      </div>
    </fieldset>
  );
}

/** Issue 478: the countries whose age ratings the portal keeps — those a profile may also be held to. */
const RATING_COUNTRIES = ["DE", "GB", "US", "ES", "IT", "BE", "CH", "NL", "CA", "AU", "FR"] as const;
type RatingCountry = (typeof RATING_COUNTRIES)[number];

function regionName(locale: string, code: string): string {
  try {
    return new Intl.DisplayNames([locale], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}

const LIMITS = ["birth", "fixed", "none"] as const;
type Limit = (typeof LIMITS)[number];
const LIMIT_ICONS: Record<Limit, string> = { birth: "cake", fixed: "shield", none: "infinity" };

/**
 * Issue 478 — a profile's age limit, one way at a time: by its birth date (one more at each birthday), a
 * fixed age, or none — never a fixed age shown beside the birth date it does not follow.
 */
function AgeLimitField({
  name,
  restrictions,
  onChange,
}: {
  name: string;
  restrictions: RestrictionSettings;
  onChange: (change: Partial<RestrictionSettings>) => void;
}) {
  const t = useT();
  const [chosen, setChosen] = useState<Limit | null>(null);
  const limit: Limit =
    chosen ?? (restrictions.birth_date ? "birth" : restrictions.max_age != null ? "fixed" : "none");
  const choose = (next: Limit) => {
    setChosen(next);
    onChange(
      next === "birth"
        ? { max_age: null }
        : next === "fixed"
          ? { birth_date: null, max_age: restrictions.max_age ?? 12 }
          : { birth_date: null, max_age: null },
    );
  };
  const age = ageOf(restrictions.birth_date);
  return (
    <>
      <fieldset className="household-editor__modes">
        <legend className="household-editor__label">{t("household:editor.limit")}</legend>
        {LIMITS.map((mode) => (
          <label key={mode} data-checked={limit === mode || undefined}>
            <input
              type="radio"
              name={name}
              value={mode}
              checked={limit === mode}
              onChange={() => choose(mode)}
            />
            <Icon name={LIMIT_ICONS[mode]} size={18} />
            <span>
              <strong>{t(`household:editor.limit_${mode}`)}</strong>
              <small>{t(`household:editor.limit_${mode}Hint`)}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {limit === "birth" ? (
        <TextField
          label={t("household:editor.birthDate")}
          hint={
            age !== null ? t("household:editor.birthDateAge", { age }) : t("household:editor.birthDateHint")
          }
          type="date"
          max={new Date().toISOString().slice(0, 10)}
          value={restrictions.birth_date ?? ""}
          onChange={(event) => onChange({ birth_date: event.target.value || null, max_age: null })}
        />
      ) : null}
      {limit === "fixed" ? (
        <SelectField
          label={t("household:editor.age")}
          value={restrictions.max_age ?? 12}
          onChange={(event) => onChange({ max_age: Number(event.target.value) })}
        >
          {AGES.map((value) => (
            <option key={value} value={value}>
              {value === 0 ? t("household:editor.ageAll") : t("household:editor.ageN", { age: value })}
            </option>
          ))}
        </SelectField>
      ) : null}
    </>
  );
}

/** Issue 478: the warnings a profile's master may keep it from — the CNC's, then each family of descriptors. */
const WARNINGS = [
  "cnc",
  "violence",
  "fear",
  "language",
  "drugs",
  "sex",
  "self_harm",
  "discrimination",
  "mature",
] as const;
type WarningKind = (typeof WARNINGS)[number];
const READINGS = ["portal", "countries", "average"] as const;
type Reading = (typeof READINGS)[number];
const READING_ICONS: Record<Reading, string> = { portal: "globe", countries: "flag", average: "scale" };

/**
 * Issue 478 — a profile's classification, in its own section: how a title's age is read (as the portal does,
 * by countries its master picks — the strictest wins —, or by the average of every country), then the
 * warnings that keep a title from the profile even when it is of its age.
 */
function ClassificationField({
  name,
  restrictions,
  onChange,
}: {
  name: string;
  restrictions: RestrictionSettings;
  onChange: (change: Partial<RestrictionSettings>) => void;
}) {
  const t = useT();
  const { locale } = useLocaleContext();
  const policy = useRatingPolicy().data;
  const household = useHousehold().data;
  const portal = (policy?.also ?? household?.rating_countries ?? []).filter((c): c is RatingCountry =>
    (RATING_COUNTRIES as readonly string[]).includes(c),
  );
  const countries = restrictions.rating_countries ?? null;
  const reading: Reading =
    restrictions.rating_blend === "average" ? "average" : countries !== null ? "countries" : "portal";
  const avoid = restrictions.avoid_warnings ?? [];
  const names = (codes: readonly string[]) => codes.map((code) => regionName(locale, code)).join(", ");
  const choose = (next: Reading) =>
    onChange(
      next === "average"
        ? { rating_blend: "average", rating_countries: null }
        : next === "countries"
          ? { rating_blend: "strictest", rating_countries: countries ?? [...portal] }
          : { rating_blend: "strictest", rating_countries: null },
    );
  // the administrator's policy: the portal's country, the order its ratings count in, the other countries
  const home = policy?.country ? regionName(locale, policy.country) : t("household:editor.portalCountry");
  const order = t(`household:editor.order.${policy?.order ?? "tv,home,cinema"}`);
  const hint = (mode: Reading) =>
    mode === "portal"
      ? [
          t("household:editor.read_portalPolicy", { country: home, order }),
          portal.length
            ? t("household:editor.read_portalAlso", { countries: names(portal) })
            : t("household:editor.read_portalAlone"),
        ].join(" ")
      : t(`household:editor.read_${mode}Hint`, { country: home });
  return (
    <fieldset className="household-editor__section household-classification">
      <legend>{t("household:editor.ratingSection")}</legend>
      <p className="household-editor__hint">{t("household:editor.ratingIntro")}</p>
      <fieldset className="household-editor__modes">
        <legend className="household-editor__label">{t("household:editor.ratingRead")}</legend>
        {READINGS.map((mode) => (
          <label key={mode} data-checked={reading === mode || undefined}>
            <input
              type="radio"
              name={name}
              value={mode}
              checked={reading === mode}
              onChange={() => choose(mode)}
            />
            <Icon name={READING_ICONS[mode]} size={18} />
            <span>
              <strong>{t(`household:editor.read_${mode}`)}</strong>
              <small>{hint(mode)}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {reading === "countries" && countries !== null ? (
        <fieldset className="household-switches household-countries__list">
          <legend className="household-editor__label">{t("household:editor.countriesPick")}</legend>
          {RATING_COUNTRIES.map((code) => (
            <Switch
              key={code}
              label={regionName(locale, code)}
              checked={countries.includes(code)}
              onChange={(event) =>
                onChange({
                  rating_countries: RATING_COUNTRIES.filter((c) =>
                    c === code ? event.target.checked : countries.includes(c),
                  ),
                })
              }
            />
          ))}
          {countries.length ? null : (
            <p className="household-editor__hint">{t("household:editor.countriesNoneHint")}</p>
          )}
        </fieldset>
      ) : null}
      <fieldset className="household-switches household-classification__warnings">
        <legend className="household-editor__label">{t("household:editor.warnings")}</legend>
        <p className="household-editor__hint">{t("household:editor.warningsHint")}</p>
        {WARNINGS.map((kind) => (
          <Switch
            key={kind}
            label={t(`household:warning.${kind}`)}
            checked={avoid.includes(kind)}
            onChange={(event) =>
              onChange({
                avoid_warnings: WARNINGS.filter((k) =>
                  k === kind ? event.target.checked : avoid.includes(k as WarningKind),
                ),
              })
            }
          />
        ))}
      </fieldset>
    </fieldset>
  );
}
