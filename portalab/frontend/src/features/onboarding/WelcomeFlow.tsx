import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import type { UiPreferences } from "../../design-system/a11y/preferences";
import { Avatar } from "../../design-system/components/Avatar";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { useShellPreference } from "../../shell/preferences";
import { ApiError } from "../../state/regions";
import { PalettePicker } from "../appearance/PalettePicker";
import { ME_KEY, type Me, useMe } from "../auth/useAuth";
import { completeStep, MISSIONS_KEY, startTour, useWelcome, WELCOME_EVENT } from "./api";
import "../appearance/notification-looks.css";
import "./onboarding.css";

/**
 * The welcome (#7): a member's first visit opens four short screens — hello (with the portal's own words),
 * a face and a name, a look, what they came for — then offers the one-minute tour. Every screen can be
 * skipped and nothing is required; once seen (``shell.onboarding.welcomedAt``) it never opens by itself
 * again, on any device, and the personal menu brings it back. An administrator can turn it off.
 */
const STEPS = ["hello", "profile", "style", "interests", "ready"] as const;
type Step = (typeof STEPS)[number];

const ART: Record<Step, string> = {
  hello: "sparkles",
  profile: "user",
  style: "palette",
  interests: "heart",
  ready: "rocket",
};

export const INTERESTS = [
  { key: "movies", icon: "film" },
  { key: "series", icon: "tv" },
  { key: "anime", icon: "sparkle" },
  { key: "documentaries", icon: "clapperboard" },
  { key: "books", icon: "book" },
  { key: "comics", icon: "library" },
  { key: "games", icon: "game" },
  { key: "music", icon: "music" },
] as const;

export function WelcomeFlow() {
  const t = useT();
  const me = useMe();
  const welcome = useWelcome();
  const navigate = useNavigate();
  const [welcomedAt, setWelcomedAt, ready] = useShellPreference<string | null>(
    "shell.onboarding.welcomedAt",
    null,
  );
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("hello");
  const decided = useRef(false);
  const titleId = useId();

  // opens by itself once, when everything needed to decide has arrived
  useEffect(() => {
    if (decided.current || !ready || !me.data || !welcome.data) return;
    decided.current = true;
    if (welcome.data.enabled && !welcomedAt && me.data.state === "active") setOpen(true);
  }, [ready, me.data, welcome.data, welcomedAt]);

  // the personal menu brings it back
  useEffect(() => {
    const reopen = () => {
      setStep("hello");
      setOpen(true);
    };
    window.addEventListener(WELCOME_EVENT, reopen);
    return () => window.removeEventListener(WELCOME_EVENT, reopen);
  }, []);

  const close = () => {
    setOpen(false);
    if (!welcomedAt) setWelcomedAt(new Date().toISOString());
  };
  const index = STEPS.indexOf(step);
  const next = () => setStep(STEPS[Math.min(index + 1, STEPS.length - 1)] as Step);
  const back = () => setStep(STEPS[Math.max(index - 1, 0)] as Step);
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
                <ol className="onboarding-dots" aria-label={t("onboarding:progress", { step: index + 1 })}>
                  {STEPS.slice(0, -1).map((s, i) => (
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
              {step === "style" ? <Style titleId={titleId} onBack={back} onNext={next} /> : null}
              {step === "interests" ? <Interests titleId={titleId} onBack={back} onNext={next} /> : null}
              {step === "ready" ? (
                <Ready
                  titleId={titleId}
                  name={name}
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
          <Icon name="trophy" size={20} />
          <span>{t("onboarding:hello.earn")}</span>
        </li>
        <li>
          <Icon name="wand" size={20} />
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
            <SelectField
              label={t("onboarding:profile.language")}
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
            >
              {(languages.data?.items ?? []).map((item) => (
                <option key={item.code} value={item.code} lang={item.code} dir={item.direction}>
                  {item.name_native}
                </option>
              ))}
            </SelectField>
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

const MODES: Array<{ key: UiPreferences["colorMode"]; icon: string }> = [
  { key: "light", icon: "sun" },
  { key: "dark", icon: "moon" },
  { key: "system", icon: "half" },
];

function Style({ titleId, onBack, onNext }: { titleId: string; onBack: () => void; onNext: () => void }) {
  const t = useT();
  const { preferences, setPreference } = usePreferences();
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
      <p className="onboarding-welcome__hint">{t("onboarding:style.more")}</p>
      <Nav onBack={onBack} onNext={onNext} />
    </>
  );
}

function Interests({ titleId, onBack, onNext }: { titleId: string; onBack: () => void; onNext: () => void }) {
  const t = useT();
  const [saved, setSaved] = useShellPreference<string[]>("shell.onboarding.interests", []);
  const [chosen, setChosen] = useState<string[]>(saved);
  const toggle = (key: string) =>
    setChosen((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]));
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:interests.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:interests.lead")}</p>
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
      <Nav
        onBack={onBack}
        onNext={() => {
          if (chosen.join() !== saved.join()) setSaved(chosen);
          if (chosen.length) void completeStep("interests").catch(() => undefined);
          onNext();
        }}
      />
    </>
  );
}

function Ready({
  titleId,
  name,
  onTour,
  onDone,
}: {
  titleId: string;
  name: string;
  onTour: () => void;
  onDone: () => void;
}) {
  const t = useT();
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:ready.title", { name })}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:ready.lead")}</p>
      <ul className="onboarding-highlights">
        <li>
          <Icon name="compass" size={20} />
          <span>{t("onboarding:ready.tour")}</span>
        </li>
        <li>
          <Icon name="target" size={20} />
          <span>{t("onboarding:ready.missions")}</span>
        </li>
      </ul>
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
