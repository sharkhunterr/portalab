import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { I18nProvider } from "../../../i18n/provider/I18nProvider";
import { ApiError } from "../../../state/regions";
import { FeaturesPicker } from "./FeaturesPicker";
import { ALL_FEATURES, applySelection, FEATURES, type Selection, toggle } from "./features";
import { holdArrival } from "./hold";
import { ImportArchive } from "./ImportArchive";
import { Launch, type Slide, useTasks } from "./Launch";
import { Stage, type StageGroup, type StageStep, StepCard } from "./Stage";
import "./arrival.css";

/**
 * Issues 246, 249 — the arrival wizard: what a new portal shows before anyone has an account, a full page of
 * its own from the first screen to the portal's opening. In the visitor's language (chosen first, read from
 * the public catalogs), it asks how the portal is installed (from scratch, or another Portalab brought in from
 * its backup — issue 247), its name, which features to keep and the administrator's account, and shows it all
 * before creating anything. Creating puts it all in place behind waiting screens (the account, the sign-in,
 * the identity, each module), then the wizard goes on signed in at ``/setup`` (services, members, access,
 * e-mail — ``ArrivalContinue``) without ever showing the portal before it is ready.
 */
type Step = "welcome" | "identity" | "features" | "admin" | "recap" | "import" | "create";
const NEW: readonly Step[] = ["welcome", "identity", "features", "admin", "recap"];
const IMPORT: readonly Step[] = ["welcome", "import"]; // issue 247: another Portalab brought in
// the way on, signed in (shown from the start so the whole way is known)
export const CONFIGURE = ["services", "members", "access", "email"] as const;
export const ARRIVAL_PATH = "/setup";

interface Account {
  login: string;
  password: string;
  confirm: string;
  displayName: string;
  email: string;
}

interface Identity {
  name: string;
  tagline: string;
  one: string;
  other: string;
  timeZone: string;
}

interface Languages {
  default: string;
  items: { code: string; name_native: string }[];
}

function initialLanguage(languages: Languages | undefined): string {
  const offered = languages?.items.map((l) => l.code) ?? [];
  const browser = (globalThis.navigator?.language ?? "").slice(0, 2).toLowerCase();
  if (offered.includes(browser)) return browser;
  return languages?.default ?? "en";
}

function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

function timeZones(current: string): string[] {
  try {
    const all = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.(
      "timeZone",
    );
    if (all?.length) return all.includes(current) ? all : [current, ...all];
  } catch {
    // older browsers: the browser's own zone and UTC
  }
  return [...new Set([current, "UTC"])];
}

/** 0–4: how strong a password looks (its length first, then the kinds of characters). */
export function strength(password: string): number {
  if (!password) return 0;
  const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length;
  let score = password.length >= 12 ? 2 : password.length >= 8 ? 1 : 0;
  if (password.length >= 16) score += 1;
  if (kinds >= 3) score += 1;
  return Math.min(4, score);
}

/** The whole way, for the side of the wizard. */
export function wayOf(current: string, install: "new" | "import", done: readonly string[] = []): StageStep[] {
  const prepare = install === "import" ? IMPORT : NEW;
  const all: Array<[string, StageGroup]> = [
    ...prepare.map((s) => [s, "prepare"] as [string, StageGroup]),
    ...(install === "new" ? CONFIGURE.map((s) => [s, "configure"] as [string, StageGroup]) : []),
    ["open", "open"],
  ];
  const at = all.findIndex(([key]) => key === current);
  return all.map(([key, group], index) => ({
    key,
    group,
    state: key === current ? "current" : index < at || done.includes(key) ? "done" : "todo",
  }));
}

export function ArrivalWizard() {
  const languages = useQuery({
    queryKey: ["i18n", "public-languages"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/i18n/public/languages" as never)).data as unknown as Languages,
  });
  const [language, setLanguage] = useState<string | null>(null);
  useEffect(() => {
    // signed in midway, the portal goes on at this address with the rest of the wizard
    if (globalThis.location?.pathname !== ARRIVAL_PATH)
      globalThis.history?.replaceState(null, "", ARRIVAL_PATH);
  }, []);
  if (languages.isPending) return <FunctionalState state="loading" detail="Portalab" />;
  const chosen = language ?? initialLanguage(languages.data);
  return (
    <I18nProvider anonymous namespaces={["core", "account"]} override={{ language: chosen, locale: chosen }}>
      <Arrival languages={languages.data} language={chosen} onLanguage={setLanguage} />
    </I18nProvider>
  );
}

function Arrival({
  languages,
  language,
  onLanguage,
}: {
  languages: Languages | undefined;
  language: string;
  onLanguage: (code: string) => void;
}) {
  const t = useT();
  const titleId = useId();
  const [step, setStep] = useState<Step>("welcome");
  const [install, setInstall] = useState<"new" | "import">("new");
  const [features, setFeatures] = useState<Selection>(ALL_FEATURES);
  const [identity, setIdentity] = useState<Identity>(() => ({
    name: "",
    tagline: "",
    one: "",
    other: "",
    timeZone: browserTimeZone(),
  }));
  const [account, setAccount] = useState<Account>({
    login: "",
    password: "",
    confirm: "",
    displayName: "",
    email: "",
  });
  const status = useQuery({
    queryKey: ["admin", "first-run"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/admin/first-run")).data as unknown as { completed: boolean },
  });

  if (status.isPending) return <FunctionalState state="loading" detail={t("account:arrival.title")} />;
  // 028: a portal already set up answers nothing to a visitor (an error, read as closed)
  if ((status.data?.completed || status.isError) && step !== "create") {
    return (
      <Stage steps={[]}>
        <StepCard id={titleId} stepKey="closed" icon="check" title={t("account:arrival.closed")}>
          <p>
            <a className="ds-button ds-button--primary" href="/">
              {t("account:arrival.signIn")}
            </a>
          </p>
        </StepCard>
      </Stage>
    );
  }

  const STEPS = install === "import" ? IMPORT : NEW;
  const index = STEPS.indexOf(step);
  const next = () => setStep(STEPS[index + 1] ?? step);
  const back = () => setStep(STEPS[index - 1] ?? step);
  const way = wayOf(step === "create" ? "recap" : step, install); // created at the recap's word
  const languageName = languages?.items.find((l) => l.code === language)?.name_native ?? language;

  if (step === "create") {
    return (
      <Stage steps={way} name={identity.name || undefined}>
        <Create
          language={language}
          identity={identity}
          account={account}
          features={features}
          onBack={() => setStep("recap")}
        />
      </Stage>
    );
  }

  const forward = (
    <Button onClick={next}>
      {t("account:arrival.next")}
      <Icon name="chevron-right" size={16} />
    </Button>
  );
  const backButton =
    index > 0 ? (
      <Button variant="ghost" onClick={back}>
        <Icon name="back" size={16} />
        {t("account:arrival.previous")}
      </Button>
    ) : (
      <span />
    );

  return (
    <Stage steps={way} name={identity.name || undefined}>
      {step === "welcome" ? (
        <StepCard
          id={titleId}
          stepKey={step}
          icon="rocket"
          title={t("account:arrival.welcome.title")}
          lead={t("account:arrival.welcome.lead")}
          footer={
            <>
              <span />
              {forward}
            </>
          }
        >
          <Welcome
            languages={languages}
            language={language}
            onLanguage={onLanguage}
            install={install}
            onInstall={setInstall}
          />
        </StepCard>
      ) : null}
      {step === "import" ? (
        <StepCard
          id={titleId}
          stepKey={step}
          icon="download"
          title={t("account:arrival.import.title")}
          lead={t("account:arrival.import.lead")}
          footer={backButton}
        >
          <ImportArchive language={language} />
        </StepCard>
      ) : null}
      {step === "identity" ? (
        <StepCard
          id={titleId}
          stepKey={step}
          icon="sparkles"
          title={t("account:arrival.identity.title")}
          lead={t("account:arrival.identity.lead")}
          footer={
            <>
              {backButton}
              <Button type="submit" form="arrival-identity">
                {t("account:arrival.next")}
                <Icon name="chevron-right" size={16} />
              </Button>
            </>
          }
        >
          <IdentityForm
            identity={identity}
            onChange={(patch) => setIdentity((i) => ({ ...i, ...patch }))}
            onSubmit={next}
          />
        </StepCard>
      ) : null}
      {step === "features" ? (
        <StepCard
          id={titleId}
          stepKey={step}
          icon="blocks"
          title={t("account:arrival.features.title")}
          lead={t("account:arrival.features.lead")}
          footer={
            <>
              {backButton}
              {forward}
            </>
          }
        >
          <FeaturesPicker
            selection={features}
            onChange={(key, on) => setFeatures((current) => toggle(current, key, on))}
          />
        </StepCard>
      ) : null}
      {step === "admin" ? (
        <StepCard
          id={titleId}
          stepKey={step}
          icon="shield"
          title={t("account:arrival.admin.title")}
          lead={t("account:arrival.admin.lead")}
          footer={
            <>
              {backButton}
              <Button type="submit" form="arrival-admin">
                {t("account:arrival.next")}
                <Icon name="chevron-right" size={16} />
              </Button>
            </>
          }
        >
          <AccountForm
            account={account}
            onChange={(patch) => setAccount((a) => ({ ...a, ...patch }))}
            onSubmit={next}
          />
        </StepCard>
      ) : null}
      {step === "recap" ? (
        <StepCard
          id={titleId}
          stepKey={step}
          icon="check"
          title={t("account:arrival.recap.title")}
          lead={t("account:arrival.recap.lead")}
          footer={
            <>
              {backButton}
              <Button onClick={() => setStep("create")}>
                <Icon name="rocket" size={16} />
                {t("account:arrival.create")}
              </Button>
            </>
          }
        >
          <dl className="arrival__recap">
            <div>
              <dt>{t("account:arrival.recap.portal")}</dt>
              <dd>
                <strong>{identity.name || "Portalab"}</strong>
                {identity.tagline ? ` — ${identity.tagline}` : ""}
              </dd>
            </div>
            <div>
              <dt>{t("account:arrival.welcome.language")}</dt>
              <dd>
                {languageName} · {identity.timeZone}
              </dd>
            </div>
            <div>
              <dt>{t("account:arrival.recap.admin")}</dt>
              <dd>
                {account.displayName || account.login} (@{account.login})
              </dd>
            </div>
            <div>
              <dt>{t("account:arrival.recap.features", { count: features.size })}</dt>
              <dd className="arrival__chips">
                {FEATURES.filter((f) => features.has(f.key)).map((f) => (
                  <span key={f.key}>
                    <Icon name={f.icon} size={14} />
                    {t(`account:features.${f.key}.title`)}
                  </span>
                ))}
              </dd>
            </div>
          </dl>
          <p className="arrival__note">
            <Icon name="info" size={16} />
            {t("account:arrival.recap.next")}
          </p>
        </StepCard>
      ) : null}
    </Stage>
  );
}

function Welcome({
  languages,
  language,
  onLanguage,
  install,
  onInstall,
}: {
  languages: Languages | undefined;
  language: string;
  onLanguage: (code: string) => void;
  install: "new" | "import";
  onInstall: (value: "new" | "import") => void;
}) {
  const t = useT();
  const id = useId();
  return (
    <>
      <div className="arrival__form">
        <label htmlFor={id}>{t("account:arrival.welcome.language")}</label>
        <select id={id} value={language} onChange={(e) => onLanguage(e.target.value)}>
          {(languages?.items ?? [{ code: language, name_native: language }]).map((l) => (
            <option key={l.code} value={l.code}>
              {l.name_native}
            </option>
          ))}
        </select>
      </div>
      <h3 className="arrival__subtitle">{t("account:arrival.welcome.install")}</h3>
      <div className="arrival__choices">
        {(["new", "import"] as const).map((value) => (
          <button
            key={value}
            type="button"
            className="arrival__choice"
            aria-pressed={install === value}
            onClick={() => onInstall(value)}
          >
            <span className="arrival__choice-icon" aria-hidden="true">
              <Icon name={value === "new" ? "sparkles" : "download"} size={22} />
            </span>
            <strong>{t(`account:arrival.install.${value}`)}</strong>
            <span>{t(`account:arrival.install.${value}Hint`)}</span>
          </button>
        ))}
      </div>
    </>
  );
}

function IdentityForm({
  identity,
  onChange,
  onSubmit,
}: {
  identity: Identity;
  onChange: (patch: Partial<Identity>) => void;
  onSubmit: () => void;
}) {
  const t = useT();
  const ids = { name: useId(), tagline: useId(), one: useId(), other: useId(), zone: useId(), hint: useId() };
  const zones = useMemo(() => timeZones(identity.timeZone), [identity.timeZone]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };
  return (
    <form id="arrival-identity" className="arrival__form arrival__form--wide" onSubmit={submit}>
      <label htmlFor={ids.name}>{t("account:arrival.identity.name")}</label>
      <input
        id={ids.name}
        maxLength={80}
        placeholder="Portalab"
        aria-describedby={ids.hint}
        value={identity.name}
        onChange={(e) => onChange({ name: e.target.value })}
      />
      <p id={ids.hint} className="field-hint">
        {t("account:arrival.identity.nameHint")}
      </p>
      <label htmlFor={ids.tagline}>{t("account:arrival.identity.tagline")}</label>
      <input
        id={ids.tagline}
        maxLength={160}
        value={identity.tagline}
        onChange={(e) => onChange({ tagline: e.target.value })}
      />
      <fieldset className="arrival__pair">
        <legend>{t("account:arrival.identity.currency")}</legend>
        <span>
          <label htmlFor={ids.one}>{t("account:arrival.identity.one")}</label>
          <input
            id={ids.one}
            maxLength={60}
            placeholder="Coin"
            value={identity.one}
            onChange={(e) => onChange({ one: e.target.value })}
          />
        </span>
        <span>
          <label htmlFor={ids.other}>{t("account:arrival.identity.other")}</label>
          <input
            id={ids.other}
            maxLength={60}
            placeholder="Coins"
            value={identity.other}
            onChange={(e) => onChange({ other: e.target.value })}
          />
        </span>
      </fieldset>
      <label htmlFor={ids.zone}>{t("account:arrival.identity.timeZone")}</label>
      <select
        id={ids.zone}
        value={identity.timeZone}
        onChange={(e) => onChange({ timeZone: e.target.value })}
      >
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    </form>
  );
}

function AccountForm({
  account,
  onChange,
  onSubmit,
}: {
  account: Account;
  onChange: (patch: Partial<Account>) => void;
  onSubmit: () => void;
}) {
  const t = useT();
  const ids = {
    login: useId(),
    password: useId(),
    confirm: useId(),
    hint: useId(),
    mismatch: useId(),
    name: useId(),
    email: useId(),
  };
  const confirmRef = useRef<HTMLInputElement>(null);
  const [tried, setTried] = useState(false);
  const mismatch = account.confirm !== "" && account.confirm !== account.password;
  const score = strength(account.password);
  useEffect(() => {
    confirmRef.current?.setCustomValidity(
      account.confirm !== account.password ? t("account:arrival.admin.mismatch") : "",
    );
  }, [account.confirm, account.password, t]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (account.confirm !== account.password) {
      setTried(true);
      confirmRef.current?.focus();
      return;
    }
    onSubmit();
  };
  return (
    <form
      id="arrival-admin"
      className="arrival__form arrival__form--wide"
      onSubmit={submit}
      onInvalid={() => setTried(true)}
    >
      <label htmlFor={ids.login}>{t("account:arrival.admin.login")}</label>
      <input
        id={ids.login}
        required
        minLength={3}
        autoComplete="username"
        value={account.login}
        onChange={(e) => onChange({ login: e.target.value.toLowerCase() })}
      />
      <label htmlFor={ids.password}>{t("account:arrival.admin.password")}</label>
      <input
        id={ids.password}
        type="password"
        required
        minLength={12}
        aria-describedby={ids.hint}
        autoComplete="new-password"
        value={account.password}
        onChange={(e) => onChange({ password: e.target.value })}
      />
      <div className="arrival__strength" data-score={score} aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>
      <p id={ids.hint} className="field-hint">
        {t("account:arrival.admin.passwordHint")}
        {account.password ? ` · ${t(`account:arrival.admin.strength.${score}`)}` : ""}
      </p>
      <label htmlFor={ids.confirm}>{t("account:arrival.admin.confirm")}</label>
      <input
        id={ids.confirm}
        ref={confirmRef}
        type="password"
        required
        autoComplete="new-password"
        aria-invalid={(mismatch && tried) || undefined}
        aria-describedby={mismatch ? ids.mismatch : undefined}
        value={account.confirm}
        onChange={(e) => onChange({ confirm: e.target.value })}
      />
      {mismatch ? (
        <p id={ids.mismatch} className="arrival__mismatch" role={tried ? "alert" : undefined}>
          {t("account:arrival.admin.mismatch")}
        </p>
      ) : account.confirm && account.confirm === account.password ? (
        <p className="arrival__match">
          <Icon name="check" size={14} />
          {t("account:arrival.admin.match")}
        </p>
      ) : null}
      <label htmlFor={ids.name}>{t("account:arrival.admin.displayName")}</label>
      <input
        id={ids.name}
        autoComplete="name"
        value={account.displayName}
        onChange={(e) => onChange({ displayName: e.target.value })}
      />
      <label htmlFor={ids.email}>{t("account:arrival.admin.email")}</label>
      <input
        id={ids.email}
        type="email"
        autoComplete="email"
        value={account.email}
        onChange={(e) => onChange({ email: e.target.value })}
      />
    </form>
  );
}

const CREATE_TASKS = ["account", "signIn", "identity", "features", "ready"] as const;

/** The portal put in place, behind the waiting screens; then the wizard goes on signed in. */
function Create({
  language,
  identity,
  account,
  features,
  onBack,
}: {
  language: string;
  identity: Identity;
  account: Account;
  features: Selection;
  onBack: () => void;
}) {
  const t = useT();
  const client = useQueryClient();
  const { states, percent, detail, run, finished } = useTasks(CREATE_TASKS);
  const created = useRef(false); // tried again after the account exists: only what is left
  const started = useRef(false);
  const create = useMutation({
    mutationFn: async () => {
      holdArrival(true);
      await run("account", async () => {
        if (created.current) return;
        await api.POST("/api/v1/admin/first-run", {
          body: {
            login: account.login,
            password: account.password,
            display_name: account.displayName || null,
            email: account.email || null,
            settings: {
              "i18n.defaultLanguage": language,
              "i18n.defaultTimeZone": identity.timeZone,
              "notifications.email.portalUrl": globalThis.location?.origin ?? "",
              "admin.setup.progress": {
                install: "new",
                step: "media",
                done: ["identity", "features", "account"],
                arrival: { step: "services" },
              },
            },
            steps: {},
          } as never,
        });
        created.current = true;
      });
      await run("signIn", async () => {
        await api.POST("/api/v1/auth/login", { body: { login: account.login, password: account.password } });
      });
      await run("identity", async () => {
        if (!identity.name.trim() && !identity.tagline.trim() && !identity.one.trim()) return;
        const currency = identity.one.trim()
          ? { [language]: { one: identity.one.trim(), other: identity.other.trim() || identity.one.trim() } }
          : {};
        await api.PUT("/api/v1/admin/site", {
          body: {
            name: identity.name.trim() || null,
            short_name: null,
            tagline: identity.tagline.trim() ? { [language]: identity.tagline.trim() } : {},
            currency,
            currency_short: null,
            currency_icon: null,
          },
        });
      });
      await run("features", async (progress) => {
        await applySelection(features, (done, total, module) =>
          progress(done / total, module ? t(`account:arrival.launch.module`, { module }) : null),
        ).catch(() => undefined); // the wizard and the setup assistant show them again
      });
      await run("ready", async () => undefined);
    },
    onError: () => holdArrival(false),
  });
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    create.mutate();
  }, [create]);
  useEffect(() => {
    if (!finished) return;
    const timer = setTimeout(() => {
      holdArrival(false); // the gate shows the portal at /setup: the wizard goes on, signed in
      void client.invalidateQueries(); // the session, the site's new name: all read again
    }, 1200);
    return () => clearTimeout(timer);
  }, [finished, client]);
  const slides = useArrivalSlides(features);
  const error =
    create.error instanceof ApiError
      ? create.error.message
      : create.isError
        ? t("account:arrival.error")
        : null;
  return (
    <section className="arrival-card arrival-card--launch" aria-label={t("account:arrival.launch.title")}>
      <Launch
        title={t("account:arrival.launch.title")}
        lead={t("account:arrival.launch.lead")}
        tasks={CREATE_TASKS.map((key) => ({
          key,
          label: t(`account:arrival.launch.task.${key}`),
          detail: states[key] === "running" ? detail : null,
          state: states[key] ?? "waiting",
        }))}
        percent={percent}
        slides={slides}
        failed={create.isError}
        done={finished}
      >
        {error ? (
          <div className="launch__error">
            <p role="alert">{error}</p>
            <div className="arrival__actions">
              <Button variant="ghost" onClick={onBack} disabled={created.current}>
                <Icon name="back" size={16} />
                {t("account:arrival.previous")}
              </Button>
              <Button onClick={() => create.mutate()}>
                <Icon name="retry" size={16} />
                {t("account:arrival.retry")}
              </Button>
            </div>
          </div>
        ) : null}
      </Launch>
    </section>
  );
}

/** What the slides tell while the portal is put in place: what it now offers, then what comes next. */
export function useArrivalSlides(features: Selection): Slide[] {
  const t = useT();
  return useMemo(
    () => [
      {
        icon: "sparkles",
        title: t("account:arrival.slide.welcome.title"),
        text: t("account:arrival.slide.welcome.text"),
      },
      ...FEATURES.filter((f) => features.has(f.key)).map((f) => ({
        icon: f.icon,
        title: t(`account:features.${f.key}.title`),
        text: t(`account:features.${f.key}.hint`),
      })),
      {
        icon: "server",
        title: t("account:arrival.slide.next.title"),
        text: t("account:arrival.slide.next.text"),
      },
    ],
    [features, t],
  );
}

export default ArrivalWizard;
