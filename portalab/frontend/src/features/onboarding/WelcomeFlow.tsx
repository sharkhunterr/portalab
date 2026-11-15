import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { UiPreferences } from "../../design-system/a11y/preferences";
import { Avatar } from "../../design-system/components/Avatar";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { useNavigationView } from "../../shell/nav/NavigationProvider";
import { useShellPreference } from "../../shell/preferences";
import { ApiError } from "../../state/regions";
import { PalettePicker } from "../appearance/PalettePicker";
import { PRESENCE_CHOICES, type PresenceLevel, setPresence, usePresence } from "../auth/CommunityPresence";
import { ME_KEY, type Me, useMe } from "../auth/useAuth";
import {
  type HouseholdMember,
  useCreateProfile,
  useHousehold,
  useHouseholdSession,
  useMakeHousehold,
  useSetPin,
} from "../household/api";
import { HouseholdEconomyChoice } from "../household/HouseholdEconomy";
import { ProfileEditor } from "../household/ProfileEditor";
import { ProfileFace } from "../household/ProfilePicker";
import { useLinks } from "../media/api";
import { RetroAccountList, useRetroAccounts } from "../retro/RetroAccounts";
import { completeStep, MISSIONS_KEY, startTour, useWelcome, WELCOME_EVENT } from "./api";
import { PlayScale } from "./PlayScale";
import { type Play, TASTES, tasteOff, tastesFor, usePlay, useProfileDashboard } from "./play";
import { Accounts, Notify } from "./WelcomeSteps";
import "../appearance/notification-looks.css";
import "./onboarding.css";

/**
 * The welcome (#7; new version, issue 243): a member's first visit opens short screens — hello (with the
 * portal's own words), a face and a name, their media accounts, how far they play, how they appear to the other
 * members (apart from the game: public or anonymous, issue 347), their portal to their taste
 * (what they came for, their home made with it), how they are told, a look (issue 347) — then everything they can set later and
 * the one-minute tour. Every screen can be skipped and nothing is required; once
 * seen (``shell.onboarding.welcomedAt``) it never opens by itself again, on any device, and the guided tours
 * page brings it back. An administrator can turn it off.
 */
const STEPS = [
  "hello",
  "profile",
  "pin",
  "accounts",
  "retro",
  "household",
  "policy",
  "family",
  "rules",
  "play",
  "presence",
  "home",
  "notify",
  "style",
  "discover",
  "ready",
] as const;
type Step = (typeof STEPS)[number];

// issue 445: the household part — asked of a master (never of a profile), and replayed on its own later
const HOUSEHOLD_STEPS: readonly Step[] = ["household", "policy", "family", "rules"];

const ART: Record<Step, string> = {
  hello: "sparkles",
  profile: "user",
  pin: "lock",
  accounts: "link",
  retro: "joystick",
  household: "home",
  policy: "coins",
  family: "users",
  rules: "shield",
  home: "heart",
  play: "gamepad",
  presence: "eye",
  notify: "bell",
  style: "palette",
  discover: "compass",
  ready: "rocket",
};

/** What the member came for: kept (``shell.onboarding.interests``) for the portal to use later. */
export const INTERESTS = [
  { key: "movies", icon: "film" },
  { key: "series", icon: "tv" },
  { key: "books", icon: "book" },
  { key: "audiobooks", icon: "headphones" },
  { key: "magazines", icon: "newspaper" },
  { key: "manga", icon: "book-open" },
  { key: "comics", icon: "message-square" },
  { key: "retro_games", icon: "joystick" },
] as const;

export function WelcomeFlow() {
  const t = useT();
  const me = useMe();
  const welcome = useWelcome();
  const navigate = useNavigate();
  // issue 246: the administrator setting the portal up is welcomed once the setup assistant is left
  const setting = useLocation().pathname.startsWith("/admin/setup");
  const [welcomedAt, setWelcomedAt, ready] = useShellPreference<string | null>(
    "shell.onboarding.welcomedAt",
    null,
  );
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("hello");
  // issue 347: the play gauge moved in this welcome — the home is then made again with it, by default
  const [replayed, setReplayed] = useState(false);
  // issue 445: only the household part (« Make a household » later), or the whole welcome
  const [only, setOnly] = useState<"household" | null>(null);
  const decided = useRef(false);
  const titleId = useId();

  // opens by itself once, when everything needed to decide has arrived
  useEffect(() => {
    if (decided.current || !ready || !me.data || !welcome.data || setting) return;
    decided.current = true;
    if (welcome.data.enabled && !welcomedAt && me.data.state === "active") setOpen(true);
  }, [ready, me.data, welcome.data, welcomedAt, setting]);

  // the personal menu brings it back
  useEffect(() => {
    const reopen = (event: Event) => {
      const part = (event as CustomEvent<"household" | null>).detail ?? null;
      setOnly(part);
      setStep(part === "household" ? "household" : "hello");
      setReplayed(false);
      setOpen(true);
    };
    window.addEventListener(WELCOME_EVENT, reopen);
    return () => window.removeEventListener(WELCOME_EVENT, reopen);
  }, []);

  const close = () => {
    setOpen(false);
    setOnly(null);
    if (!welcomedAt) setWelcomedAt(new Date().toISOString());
  };
  // issue 347: no presence screen when the privacy centre is off
  const presence = usePresence();
  // 032: a household profile uses its master's media accounts, and its master decides its presence
  const profile = Boolean(me.data?.profile_of);
  // issue 426: the game library accounts the administrator mapped this member to, to authorise Portalab on
  const retro = useRetroAccounts();
  const links = useLinks();
  // never a crash of the whole portal on an unexpected answer: lists only
  const retroAccounts = Array.isArray(retro.data) ? retro.data : [];
  const myLinks = Array.isArray(links.data) ? links.data : [];
  const mapped = retroAccounts
    .filter((a) => myLinks.some((l) => l.verified && l.service_id === a.service_id))
    .map((a) => a.service_id);
  const toAuthorise = retroAccounts.some((a) => mapped.includes(a.service_id) && a.state !== "linked");
  // issue 428: the account's holder makes its household's profiles here (not a profile itself)
  const session = useHouseholdSession(open && !profile);
  const family = Boolean(session.data?.enabled) && !profile;
  const made = Boolean(session.data?.made);
  const steps = STEPS.filter(
    (s) =>
      (only !== "household" || HOUSEHOLD_STEPS.includes(s)) &&
      (!HOUSEHOLD_STEPS.includes(s) || family) &&
      // issue 445: asked while there is no household; its policy, profiles and rules once it is made
      (s !== "household" || !made || step === "household") &&
      (!["policy", "family", "rules"].includes(s) || made) &&
      (s !== "presence" || presence.available) &&
      (s !== "retro" || (!profile && mapped.length > 0 && (toAuthorise || step === "retro"))) &&
      !(profile && (s === "accounts" || s === "presence")) &&
      (s !== "pin" || profile), // issue 446: a profile's own PIN, its master's account is its master's
  );
  const index = Math.max(steps.indexOf(step), 0);
  const last = index >= steps.length - 1;
  const next = () =>
    only === "household" && last ? close() : setStep(steps[Math.min(index + 1, steps.length - 1)] as Step);
  // issue 445: no household — its policy, profiles and rules are skipped, the welcome goes on
  const afterHousehold = () => {
    const rest = steps.filter((s) => STEPS.indexOf(s) > STEPS.indexOf("rules"));
    if (only === "household" || !rest.length) close();
    else setStep(rest[0] as Step);
  };
  const back = () => setStep(steps[Math.max(index - 1, 0)] as Step);
  const name = me.data?.display_name ?? me.data?.login ?? "";

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(next) => (next ? setOpen(true) : close())}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ds-overlay onboarding-overlay" />
        <DialogPrimitive.Content
          className="onboarding-welcome"
          aria-labelledby={titleId}
          aria-describedby={undefined}
          data-step={step}
          onOpenAutoFocus={(event) => {
            // the dialog itself takes the focus (not « Skip »): Tab then reaches the screen's controls
            event.preventDefault();
            (event.currentTarget as HTMLElement | null)?.focus();
          }}
        >
          <div className="onboarding-welcome__art" aria-hidden="true">
            <span className="onboarding-welcome__orb" />
            <span className="onboarding-welcome__icon" key={step}>
              <Icon name={ART[step]} size={44} />
            </span>
          </div>
          <div className="onboarding-welcome__body">
            <div className="onboarding-welcome__top">
              {step === "ready" ? (
                <span />
              ) : (
                <ol
                  className="onboarding-dots"
                  aria-label={t("onboarding:progress", { step: index + 1, total: steps.length - 1 })}
                >
                  {steps.slice(0, -1).map((s, i) => (
                    <li key={s} data-state={i < index ? "done" : i === index ? "current" : undefined} />
                  ))}
                </ol>
              )}
              <button type="button" className="onboarding-skip" onClick={close}>
                {step === "ready" ? t("onboarding:close") : t("onboarding:skip")}
              </button>
            </div>
            <div className="onboarding-welcome__screen" key={step}>
              {step === "hello" ? (
                <Hello titleId={titleId} name={name} message={welcome.data?.message ?? ""} onNext={next} />
              ) : null}
              {step === "profile" && me.data ? (
                <Profile titleId={titleId} me={me.data} onBack={back} onNext={next} />
              ) : null}
              {step === "pin" && me.data ? (
                <PinStep titleId={titleId} me={me.data.id} nav={<Nav onBack={back} onNext={next} />} />
              ) : null}
              {step === "accounts" ? (
                <Accounts titleId={titleId} nav={<Nav onBack={back} onNext={next} />} />
              ) : null}

              {step === "retro" ? (
                <RetroStep titleId={titleId} only={mapped} nav={<Nav onBack={back} onNext={next} />} />
              ) : null}
              {step === "household" ? (
                <HouseholdAsk titleId={titleId} onMade={() => setStep("policy")} onNone={afterHousehold} />
              ) : null}
              {step === "policy" ? (
                <PolicyStep titleId={titleId} nav={<Nav onBack={back} onNext={next} />} />
              ) : null}
              {step === "family" ? (
                <FamilyStep titleId={titleId} nav={<Nav onBack={back} onNext={next} />} />
              ) : null}
              {step === "rules" ? (
                <RulesStep titleId={titleId} nav={<Nav onBack={back} onNext={next} />} />
              ) : null}
              {step === "play" ? (
                <PlayChoice
                  titleId={titleId}
                  onBack={back}
                  onNext={(changed) => {
                    if (changed) setReplayed(true);
                    next();
                  }}
                />
              ) : null}
              {step === "presence" ? <Presence titleId={titleId} onBack={back} onNext={next} /> : null}
              {step === "home" ? (
                <Home titleId={titleId} first={!welcomedAt} remake={replayed} onBack={back} onNext={next} />
              ) : null}
              {step === "notify" ? (
                <Notify
                  titleId={titleId}
                  first={!welcomedAt}
                  onNext={next}
                  renderNav={(go) => <Nav onBack={back} onNext={go} />}
                />
              ) : null}
              {step === "style" ? <Style titleId={titleId} onBack={back} onNext={next} /> : null}
              {step === "discover" ? (
                <Discover titleId={titleId} profile={profile} nav={<Nav onBack={back} onNext={next} />} />
              ) : null}
              {step === "ready" ? (
                <Ready
                  titleId={titleId}
                  name={name}
                  onLeave={close}
                  onTour={() => {
                    close();
                    navigate("/");
                    startTour();
                  }}
                  onDone={close}
                />
              ) : null}
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function Nav({ onBack, onNext, label }: { onBack?: () => void; onNext: () => void; label?: string }) {
  const t = useT();
  return (
    <div className="onboarding-welcome__nav">
      {onBack ? (
        <Button variant="ghost" onClick={onBack}>
          <Icon name="chevron-left" size={18} />
          {t("onboarding:back")}
        </Button>
      ) : (
        <span />
      )}
      <Button onClick={onNext}>
        {label ?? t("onboarding:next")}
        <Icon name="chevron-right" size={18} />
      </Button>
    </div>
  );
}

function Hello({
  titleId,
  name,
  message,
  onNext,
}: {
  titleId: string;
  name: string;
  message: string;
  onNext: () => void;
}) {
  const t = useT();
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:hello.title", { name })}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:hello.lead")}</p>
      {message ? <blockquote className="onboarding-welcome__message">{message}</blockquote> : null}
      <ul className="onboarding-highlights">
        <li>
          <Icon name="film" size={20} />
          <span>{t("onboarding:hello.watch")}</span>
        </li>
        <li>
          <Icon name="gamepad" size={20} />
          <span>{t("onboarding:hello.play")}</span>
        </li>
        <li>
          <Icon name="sliders" size={20} />
          <span>{t("onboarding:hello.make")}</span>
        </li>
      </ul>
      <Nav onNext={onNext} label={t("onboarding:hello.start")} />
    </>
  );
}

interface LanguageItem {
  code: string;
  name_native: string;
  direction: "ltr" | "rtl";
}

function Profile({
  titleId,
  me,
  onBack,
  onNext,
}: {
  titleId: string;
  me: Me;
  onBack: () => void;
  onNext: () => void;
}) {
  const t = useT();
  const client = useQueryClient();
  const ctx = useLocaleContext();
  const fileId = useId();
  const [displayName, setDisplayName] = useState(me.display_name ?? me.login ?? "");
  const [language, setLanguage] = useState(ctx.language);
  const [version, setVersion] = useState(0);
  const languages = useQuery({
    queryKey: ["i18n", "languages"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/i18n/languages")).data as unknown as { default: string; items: LanguageItem[] },
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      await api.PUT("/api/v1/me/avatar", {
        body: file as unknown as string,
        bodySerializer: (body) => body as unknown as BodyInit,
        headers: { "Content-Type": file.type || "application/octet-stream" },
      });
    },
    onSuccess: async () => {
      setVersion(Date.now());
      await client.invalidateQueries({ queryKey: ME_KEY });
      await client.invalidateQueries({ queryKey: MISSIONS_KEY });
    },
  });
  const save = useMutation({
    mutationFn: async () => {
      const name = displayName.trim();
      if (name && name !== (me.display_name ?? me.login ?? "")) {
        await api.PATCH("/api/v1/me/profile", { body: { display_name: name } });
      }
      if (language !== ctx.language) {
        await api.PUT("/api/v1/me/preferences", { body: { "i18n.language": language } as never });
      }
    },
    onSuccess: async () => {
      void completeStep("profile").catch(() => undefined);
      await client.invalidateQueries({ queryKey: ME_KEY });
      await client.invalidateQueries({ queryKey: ["me", "preferences"] });
      await client.invalidateQueries({ queryKey: ["i18n"] });
      await client.invalidateQueries({ queryKey: MISSIONS_KEY });
      onNext();
    },
  });
  const error = upload.error ?? save.error;
  const problem =
    error instanceof ApiError && error.code === "user.display_name_taken"
      ? t("onboarding:profile.nameTaken")
      : error instanceof ApiError && error.code === "user.avatar_invalid"
        ? t("onboarding:profile.avatarInvalid")
        : error
          ? t("onboarding:profile.error")
          : null;
  const avatar = me.has_avatar ? `/api/v1/users/${me.id}/avatar${version ? `?v=${version}` : ""}` : null;
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:profile.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:profile.lead")}</p>
      <div className="onboarding-profile">
        <label
          htmlFor={fileId}
          className="onboarding-profile__avatar"
          data-busy={upload.isPending || undefined}
        >
          <Avatar name={displayName || me.login || ""} userId={me.id} src={avatar} size="xl" decorative />
          <span className="onboarding-profile__camera" aria-hidden="true">
            <Icon name={upload.isPending ? "spinner" : "image"} size={18} />
          </span>
          <span className="visually-hidden">{t("onboarding:profile.photo")}</span>
        </label>
        <input
          id={fileId}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="visually-hidden"
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            const file = event.target.files?.[0];
            if (file) upload.mutate(file);
            event.target.value = "";
          }}
        />
        <div className="onboarding-profile__fields">
          <TextField
            label={t("onboarding:profile.name")}
            value={displayName}
            maxLength={64}
            autoComplete="nickname"
            onChange={(event) => setDisplayName(event.target.value)}
          />
          {(languages.data?.items.length ?? 0) > 1 ? (
            // issue 449: each language by its flag and its own name, chosen in a tap
            <fieldset className="onboarding-languages">
              <legend>{t("onboarding:profile.language")}</legend>
              {(languages.data?.items ?? []).map((item) => (
                <label key={item.code} data-checked={language === item.code || undefined}>
                  <input
                    type="radio"
                    name={`${fileId}-language`}
                    value={item.code}
                    checked={language === item.code}
                    onChange={() => setLanguage(item.code)}
                  />
                  <span className="onboarding-languages__flag" aria-hidden="true">
                    {flagOf(item.code)}
                  </span>
                  <span lang={item.code} dir={item.direction}>
                    {item.name_native}
                  </span>
                </label>
              ))}
            </fieldset>
          ) : null}
        </div>
      </div>
      {problem ? (
        <p className="onboarding-welcome__problem" role="alert">
          {problem}
        </p>
      ) : null}
      <div className="onboarding-welcome__nav">
        <Button variant="ghost" onClick={onBack}>
          <Icon name="chevron-left" size={18} />
          {t("onboarding:back")}
        </Button>
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {t("onboarding:next")}
          <Icon name="chevron-right" size={18} />
        </Button>
      </div>
    </>
  );
}

// issue 449: a language's flag — its likeliest country (English: the United Kingdom); none when unknown
const FLAG_COUNTRY: Record<string, string> = {
  en: "GB",
  fr: "FR",
  de: "DE",
  es: "ES",
  it: "IT",
  pt: "PT",
  nl: "NL",
  pl: "PL",
  sv: "SE",
  da: "DK",
  nb: "NO",
  no: "NO",
  fi: "FI",
  cs: "CZ",
  ja: "JP",
  ko: "KR",
  zh: "CN",
  ru: "RU",
  uk: "UA",
  tr: "TR",
  ar: "SA",
  he: "IL",
  el: "GR",
  hu: "HU",
  ro: "RO",
};

function flagOf(code: string): string {
  const parts = code.split(/[-_]/);
  const region =
    parts[1]?.length === 2 ? parts[1].toUpperCase() : FLAG_COUNTRY[parts[0]?.toLowerCase() ?? ""];
  if (!region) return "🌐";
  return String.fromCodePoint(...[...region].map((letter) => 0x1f1e6 + letter.charCodeAt(0) - 65));
}

const MODES: Array<{ key: UiPreferences["colorMode"]; icon: string }> = [
  { key: "light", icon: "sun" },
  { key: "dark", icon: "moon" },
  { key: "system", icon: "half" },
];

function Style({ titleId, onBack, onNext }: { titleId: string; onBack: () => void; onNext: () => void }) {
  const t = useT();
  const { preferences, setPreference, policy } = usePreferences();
  const scaleId = useId();
  const scale = preferences.textScale ?? 1; // 100 % until the member moves it
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:style.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:style.lead")}</p>
      <fieldset className="onboarding-modes">
        <legend className="visually-hidden">{t("onboarding:style.mode")}</legend>
        {MODES.map((mode) => (
          <label
            key={mode.key}
            className="onboarding-tile"
            data-current={preferences.colorMode === mode.key || undefined}
          >
            <input
              type="radio"
              name="onboarding-mode"
              value={mode.key}
              checked={preferences.colorMode === mode.key}
              onChange={() => setPreference("colorMode", mode.key)}
            />
            <span className="onboarding-tile__preview" data-mode={mode.key} aria-hidden="true">
              <Icon name={mode.icon} size={22} />
            </span>
            <span>{t(`onboarding:style.${mode.key}`)}</span>
          </label>
        ))}
      </fieldset>
      <div className="onboarding-palettes">
        <PalettePicker />
      </div>
      {/* issue 447: the text size, as in the appearance settings (the administrator's bounds) */}
      <div className="ds-field onboarding-scale">
        <label htmlFor={scaleId}>{t("onboarding:style.textScale")}</label>
        <span className="onboarding-scale__row">
          <span aria-hidden="true">A</span>
          <input
            id={scaleId}
            type="range"
            min={policy.textScaleMin}
            max={policy.textScaleMax}
            step={0.05}
            value={scale}
            aria-valuetext={`${Math.round(scale * 100)}%`}
            onChange={(event) => setPreference("textScale", Number(event.target.value))}
          />
          <span aria-hidden="true" className="onboarding-scale__big">
            A
          </span>
          <output htmlFor={scaleId}>{Math.round(scale * 100)}%</output>
        </span>
      </div>
      <p className="onboarding-welcome__hint">{t("onboarding:style.more")}</p>
      <Nav onBack={onBack} onNext={onNext} />
    </>
  );
}

/**
 * Issue 347: « your portal to your taste » — what the member watches and reads (kept for the portal to use
 * later), what they want on their home (each taste brings its widgets), and their home made with it: the
 * dashboard the administrator prepared for their play profile, to these tastes (at once on a first visit,
 * nothing to lose; asked otherwise, it replaces their arrangement — ticked when the play gauge just moved).
 * « Just the media » leaves the game and the community out.
 */
function Home({
  titleId,
  first,
  remake,
  onBack,
  onNext,
}: {
  titleId: string;
  first: boolean;
  remake: boolean;
  onBack: () => void;
  onNext: () => void;
}) {
  const t = useT();
  const { saved: play } = usePlay();
  const [saved, setSaved] = useShellPreference<string[]>("shell.onboarding.interests", []);
  const [savedTastes, setTastes] = useShellPreference<string[] | null>("shell.onboarding.tastes", null);
  const [chosen, setChosen] = useState<string[]>(() =>
    saved.filter((key) => INTERESTS.some((interest) => interest.key === key)),
  );
  const level = play ?? "full";
  const [tastes, setTastesChosen] = useState<string[]>(() =>
    (savedTastes ?? tastesFor(level)).filter((key) => !tasteOff(level, key)),
  );
  const [arrange, setArrange] = useState(first || remake);
  const dashboard = useProfileDashboard();
  const toggle = (key: string) =>
    setChosen((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]));
  const flip = (key: string) =>
    setTastesChosen((current) =>
      current.includes(key) ? current.filter((k) => k !== key) : [...current, key],
    );
  const go = async () => {
    if (chosen.join() !== saved.join()) setSaved(chosen);
    if (chosen.length) void completeStep("interests").catch(() => undefined);
    if (tastes.join() !== (savedTastes ?? []).join()) setTastes(tastes);
    if (arrange) await dashboard.mutateAsync(tastes);
    onNext();
  };
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:home.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:home.lead")}</p>
      <h3 className="onboarding-welcome__part">{t("onboarding:interests.title")}</h3>
      <fieldset className="onboarding-chips">
        <legend className="visually-hidden">{t("onboarding:interests.title")}</legend>
        {INTERESTS.map((interest) => (
          <label
            key={interest.key}
            className="onboarding-chip"
            data-on={chosen.includes(interest.key) || undefined}
          >
            <input
              type="checkbox"
              checked={chosen.includes(interest.key)}
              onChange={() => toggle(interest.key)}
            />
            <Icon name={interest.icon} size={18} />
            <span>{t(`onboarding:interests.${interest.key}`)}</span>
          </label>
        ))}
      </fieldset>
      <h3 className="onboarding-welcome__part">{t("onboarding:home.tastes")}</h3>
      <fieldset className="onboarding-chips">
        <legend className="visually-hidden">{t("onboarding:home.tastes")}</legend>
        {TASTES.map((taste) => {
          const off = tasteOff(level, taste.key);
          return (
            <label
              key={taste.key}
              className="onboarding-chip"
              data-on={tastes.includes(taste.key) || undefined}
              data-off={off || undefined}
              title={off ? t("onboarding:home.playOff") : undefined}
            >
              <input
                type="checkbox"
                checked={tastes.includes(taste.key)}
                disabled={off}
                onChange={() => flip(taste.key)}
              />
              <Icon name={taste.icon} size={18} />
              <span>{t(`onboarding:home.taste.${taste.key}`)}</span>
            </label>
          );
        })}
      </fieldset>
      <label className="onboarding-check">
        <input type="checkbox" checked={arrange} onChange={(event) => setArrange(event.target.checked)} />
        <span className="onboarding-check__text">
          <strong>{t("onboarding:home.arrange")}</strong>
          <span className="onboarding-check__hint">
            {t(first ? "onboarding:home.arrangeHint" : "onboarding:home.arrangeReplace")}
          </span>
        </span>
      </label>
      {dashboard.error ? (
        <p className="onboarding-welcome__problem" role="alert">
          {t("onboarding:play.error")}
        </p>
      ) : null}
      <Nav onBack={onBack} onNext={() => void go().catch(() => undefined)} />
    </>
  );
}

/** How far the member plays; public or anonymous is the next screen, apart from the game (issue 347). */
function PlayChoice({
  titleId,
  onBack,
  onNext,
}: {
  titleId: string;
  onBack: () => void;
  onNext: (changed: boolean) => void;
}) {
  const t = useT();
  const { saved, save } = usePlay();
  const [chosen, setChosen] = useState<Play>(saved ?? "full");
  const go = async () => {
    if (chosen !== saved) await save.mutateAsync(chosen);
    onNext(chosen !== saved);
  };
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:play.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:play.lead")}</p>
      <PlayScale value={chosen} onChange={setChosen} disabled={save.isPending} />
      {save.error ? (
        <p className="onboarding-welcome__problem" role="alert">
          {t("onboarding:play.error")}
        </p>
      ) : null}
      <Nav onBack={onBack} onNext={() => void go().catch(() => undefined)} />
    </>
  );
}

/** Issue 347: what each answer shows of the member to the others — and what it does not. */
const PRESENCE_SHOWS = {
  public: ["directory", "activity", "leaderboards"],
  anonymous: ["directory", "activity", "leaderboards"],
} as const;

/**
 * Issue 347: how the member appears to the others — a screen of its own, apart from the game: whatever the
 * play gauge, public (named in the community, for the portal's members only) or anonymous (absent from the
 * directory and the activity, counted unnamed in the leaderboards). It starts on the member's present answer
 * and is kept on « Next ».
 */
function Presence({ titleId, onBack, onNext }: { titleId: string; onBack: () => void; onNext: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const presence = usePresence();
  const [seen, setSeen] = useState<PresenceLevel | null>(null);
  const shown = seen ?? presence.current;
  const keep = useMutation({
    mutationFn: setPresence,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["privacy", "me"] });
      void client.invalidateQueries({ queryKey: ["community"] });
    },
  });
  const go = async () => {
    if (seen !== null && seen !== presence.current) await keep.mutateAsync(seen);
    onNext();
  };
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:presence.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:presence.lead")}</p>
      <fieldset className="onboarding-presence" disabled={presence.locked || keep.isPending}>
        <legend className="visually-hidden">{t("onboarding:presence.title")}</legend>
        {PRESENCE_CHOICES.map((choice) => (
          <label
            key={choice.key}
            className="onboarding-tile"
            data-current={shown === choice.level || undefined}
          >
            <input
              type="radio"
              name="onboarding-presence"
              checked={shown === choice.level}
              onChange={() => setSeen(choice.level)}
            />
            <span className="onboarding-presence__head">
              <Icon name={choice.icon} size={20} />
              <strong>{t(`account:presence.${choice.key}`)}</strong>
            </span>
            <span className="onboarding-presence__summary">{t(`onboarding:presence.${choice.key}`)}</span>
            <ul className="onboarding-presence__list">
              {PRESENCE_SHOWS[choice.key].map((place) => (
                <li key={place}>
                  <Icon name={choice.key === "public" ? "check" : "hide"} size={14} />
                  {t(`onboarding:presence.${choice.key}.${place}`)}
                </li>
              ))}
            </ul>
          </label>
        ))}
      </fieldset>
      <ul className="onboarding-presence__facts">
        <li>
          <Icon name="gamepad" size={16} />
          {t("onboarding:presence.apart")}
        </li>
        <li>
          <Icon name="lock" size={16} />
          {t("onboarding:presence.inside")}
        </li>
      </ul>
      <p className="onboarding-welcome__hint">
        {presence.locked ? t("account:presence.locked") : t("onboarding:presence.later")}{" "}
        <Link to="/privacy">{t("onboarding:presence.privacy")}</Link>
      </p>
      {keep.error ? (
        <p className="onboarding-welcome__problem" role="alert">
          {t("onboarding:play.error")}
        </p>
      ) : null}
      <Nav onBack={onBack} onNext={() => void go().catch(() => undefined)} />
    </>
  );
}

/** Everything the member can set later, each where it is set. */
const SETTINGS = [
  { key: "look", icon: "palette", to: "/settings/appearance" },
  { key: "dashboard", icon: "dashboard", to: "/" },
  { key: "notifications", icon: "mail", to: "/settings/notifications" },
  { key: "privacy", icon: "shield", to: "/privacy" },
] as const;

function Ready({
  titleId,
  name,
  onTour,
  onDone,
  onLeave,
}: {
  titleId: string;
  name: string;
  onTour: () => void;
  onDone: () => void;
  onLeave: () => void;
}) {
  const t = useT();
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:ready.title", { name })}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:ready.lead")}</p>
      <ul className="onboarding-settings">
        {SETTINGS.map((setting) => (
          <li key={setting.key}>
            <Link to={setting.to} onClick={onLeave}>
              <Icon name={setting.icon} size={20} />
              <span>
                <strong>{t(`onboarding:ready.${setting.key}`)}</strong>
                <span>{t(`onboarding:ready.${setting.key}Hint`)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="onboarding-welcome__hint">{t("onboarding:ready.tour")}</p>
      <div className="onboarding-welcome__nav">
        <Button variant="ghost" onClick={onDone}>
          {t("onboarding:ready.later")}
        </Button>
        <Button onClick={onTour}>
          <Icon name="compass" size={18} />
          {t("onboarding:ready.go")}
        </Button>
      </div>
    </>
  );
}

/** Issue 426: play with one's own RomM account — the code approved in RomM, once (the administrator mapped
 * this member to an account there). */
function RetroStep({ titleId, only, nav }: { titleId: string; only: readonly string[]; nav: ReactNode }) {
  const t = useT();
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:retro.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:retro.lead")}</p>
      <RetroAccountList only={only} />
      {nav}
    </>
  );
}

/** Issue 450: how the portal works, before it opens — what this member's menu holds (watching, playing, the
 * wiki, help, the community) and how they progress (XP, Coins, Contribution); for a household profile, its
 * household's share. */
const DISCOVER: Array<{ key: string; icon: string; route?: string }> = [
  { key: "menu", icon: "menu" },
  { key: "media", icon: "play", route: "/media" },
  { key: "games", icon: "gamepad", route: "/games" },
  { key: "wiki", icon: "book-open", route: "/wiki" },
  { key: "support", icon: "lifebuoy", route: "/support" },
  { key: "community", icon: "users", route: "/community" },
  { key: "progress", icon: "trophy", route: "/progression" },
];

function Discover({ titleId, profile, nav }: { titleId: string; profile: boolean; nav: ReactNode }) {
  const t = useT();
  const navigation = useNavigationView();
  const household = useHousehold(profile);
  const routes = new Set(
    navigation.view.sections.flatMap((section) => [
      ...section.entries.map((entry) => entry.route),
      ...section.topics.flatMap((topic) => topic.entries.map((entry) => entry.route)),
    ]),
  );
  const known = routes.size > 0; // the menu not there yet: every part is told
  const pot = profile && (household.data?.economy ?? "pot") === "pot";
  const parts = DISCOVER.filter((part) => !part.route || !known || routes.has(part.route));
  const text = (key: string) => {
    if (key === "community" && profile) return t("onboarding:discover.communityProfile");
    if (key === "progress" && profile)
      return t(pot ? "onboarding:discover.progressPot" : "onboarding:discover.progressOwn");
    return t(`onboarding:discover.${key}`);
  };
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:discover.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:discover.lead")}</p>
      <ul className="onboarding-discover">
        {parts.map((part) => (
          <li key={part.key}>
            <span className="onboarding-discover__icon" aria-hidden="true">
              <Icon name={part.icon} size={20} />
            </span>
            <span>
              <strong>{t(`onboarding:discover.${part.key}Title`)}</strong>
              <span>{text(part.key)}</span>
            </span>
          </li>
        ))}
      </ul>
      {nav}
    </>
  );
}

/** Issue 446: a profile's own PIN — so that no one else in the household enters it (changed later from the
 * avatar's menu); one its master set already is replaced by giving it. Skippable. */
function PinStep({ titleId, me, nav }: { titleId: string; me: string; nav: ReactNode }) {
  const t = useT();
  const household = useHousehold();
  const setPin = useSetPin();
  const [current, setCurrent] = useState("");
  const [pin, setPinValue] = useState("");
  const [again, setAgain] = useState("");
  const [saved, setSaved] = useState(false);
  const mine = household.data?.members.find((m) => m.id === me);
  const has = Boolean(mine?.has_pin) && !saved;
  const valid = /^\d{4,6}$/.test(pin);
  const mismatch = again !== "" && again !== pin;
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:pin.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t(has ? "onboarding:pin.leadHas" : "onboarding:pin.lead")}</p>
      {saved ? (
        <p className="onboarding-welcome__lead" role="status">
          <Icon name="check" size={16} /> {t("onboarding:pin.saved")}
        </p>
      ) : (
        <form
          className="onboarding-pin"
          onSubmit={(event) => {
            event.preventDefault();
            if (!valid || pin !== again) return;
            setPin.mutate({ id: me, pin, ...(has ? { current } : {}) }, { onSuccess: () => setSaved(true) });
          }}
        >
          {has ? (
            <TextField
              label={t("household:myPin.current")}
              type="password"
              inputMode="numeric"
              autoComplete="off"
              maxLength={6}
              value={current}
              onChange={(event) => setCurrent(event.target.value.replace(/\D/g, ""))}
            />
          ) : null}
          <TextField
            label={t("household:myPin.new")}
            hint={t("onboarding:pin.hint")}
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={6}
            value={pin}
            onChange={(event) => setPinValue(event.target.value.replace(/\D/g, ""))}
          />
          <TextField
            label={t("onboarding:pin.again")}
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={6}
            value={again}
            error={mismatch ? t("onboarding:pin.mismatch") : undefined}
            onChange={(event) => setAgain(event.target.value.replace(/\D/g, ""))}
          />
          <Button type="submit" variant="secondary" disabled={!valid || pin !== again || setPin.isPending}>
            <Icon name="lock" size={16} />
            {t("onboarding:pin.save")}
          </Button>
          {setPin.isError ? <p role="alert">{t("household:myPin.refused")}</p> : null}
        </form>
      )}
      {nav}
    </>
  );
}

/** Issue 445: a household or not — made with a common pot (changed on the next screen), or none: its screens
 * are skipped and « My household » stays out of the menu (made later from the account page). */
function HouseholdAsk({
  titleId,
  onMade,
  onNone,
}: {
  titleId: string;
  onMade: () => void;
  onNone: () => void;
}) {
  const t = useT();
  const make = useMakeHousehold();
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:household.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:household.lead")}</p>
      <div className="onboarding-household">
        <button
          type="button"
          className="onboarding-household__choice"
          disabled={make.isPending}
          onClick={() => make.mutate("pot", { onSuccess: onMade })}
        >
          <Icon name="users" size={22} />
          <span>
            <strong>{t("onboarding:household.yes")}</strong>
            <small>{t("onboarding:household.yesHint")}</small>
          </span>
        </button>
        <button type="button" className="onboarding-household__choice" onClick={onNone}>
          <Icon name="user" size={22} />
          <span>
            <strong>{t("onboarding:household.no")}</strong>
            <small>{t("onboarding:household.noHint")}</small>
          </span>
        </button>
      </div>
      {make.isError ? <p role="alert">{t("household:error")}</p> : null}
    </>
  );
}

/** Issue 445: the household's policy — a common pot on the master's account, or separate profiles. */
function PolicyStep({ titleId, nav }: { titleId: string; nav: ReactNode }) {
  const t = useT();
  const household = useHousehold();
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:policy.title")}</DialogPrimitive.Title>
      {household.data ? <HouseholdEconomyChoice household={household.data} /> : null}
      {nav}
    </>
  );
}

/** Issue 445: each profile's rules — its kind's presets, set in place (ages, genres, screen time…). */
function RulesStep({ titleId, nav }: { titleId: string; nav: ReactNode }) {
  const t = useT();
  const household = useHousehold();
  const [editing, setEditing] = useState<HouseholdMember | null>(null);
  const data = household.data;
  const profiles = (data?.members ?? []).filter((m) => m.kind !== "owner");
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:rules.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">
        {profiles.length ? t("onboarding:rules.lead") : t("onboarding:rules.none")}
      </p>
      {profiles.length ? (
        <ul className="onboarding-family" aria-label={t("onboarding:family.made")}>
          {profiles.map((member) => (
            <li key={member.id}>
              <ProfileFace member={member} size="sm" />
              <span>{member.display_name}</span>
              <small>{t(`household:kind.${member.kind}`)}</small>
              <Button variant="secondary" onClick={() => setEditing(member)}>
                <Icon name="settings" size={14} />
                {t("onboarding:rules.set", { name: member.display_name })}
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {editing && data ? (
        <ProfileEditor
          member={editing}
          position={profiles.indexOf(editing) + 1}
          palette={data.palette}
          economy={data.economy ?? "pot"}
          onClose={() => setEditing(null)}
        />
      ) : null}
      {nav}
    </>
  );
}

/** Issue 428: the household — a profile for each person sharing the account (a name and a kind; the rest is
 * set later in « My household »). */
function FamilyStep({ titleId, nav }: { titleId: string; nav: ReactNode }) {
  const t = useT();
  const household = useHousehold();
  const create = useCreateProfile();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"standard" | "child">("child");
  const profiles = (household.data?.members ?? []).filter((m) => m.kind !== "owner");
  const full = household.data ? profiles.length >= household.data.max_profiles : false;
  const add = () => {
    if (!name.trim() || full) return;
    create.mutate({ display_name: name.trim(), kind }, { onSuccess: () => setName("") });
  };
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:family.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:family.lead")}</p>
      {profiles.length ? (
        <ul className="onboarding-family" aria-label={t("onboarding:family.made")}>
          {profiles.map((member) => (
            <li key={member.id}>
              <ProfileFace member={member} size="sm" />
              <span>{member.display_name}</span>
              <small>{t(`household:kind.${member.kind}`)}</small>
            </li>
          ))}
        </ul>
      ) : null}
      {full ? (
        <p className="onboarding-welcome__lead">{t("onboarding:family.full")}</p>
      ) : (
        <form
          className="onboarding-family__add"
          onSubmit={(event) => {
            event.preventDefault();
            add();
          }}
        >
          <TextField
            label={t("onboarding:family.name")}
            value={name}
            maxLength={64}
            onChange={(event) => setName(event.target.value)}
          />
          <fieldset className="onboarding-family__kinds">
            <legend className="visually-hidden">{t("household:editor.kind")}</legend>
            {(["child", "standard"] as const).map((option) => (
              <label key={option} data-checked={kind === option || undefined}>
                <input
                  type="radio"
                  name={`${titleId}-kind`}
                  checked={kind === option}
                  onChange={() => setKind(option)}
                />
                <Icon name={option === "child" ? "smile" : "user"} size={16} />
                {t(`household:kind.${option}`)}
              </label>
            ))}
          </fieldset>
          <Button type="submit" variant="secondary" disabled={!name.trim() || create.isPending}>
            <Icon name="plus" size={16} />
            {t("onboarding:family.add")}
          </Button>
          {create.isError ? <p role="alert">{t("household:error")}</p> : null}
        </form>
      )}
      <p className="onboarding-welcome__hint">
        <Link to="/household/profiles">{t("onboarding:family.later")}</Link>
      </p>
      {nav}
    </>
  );
}
