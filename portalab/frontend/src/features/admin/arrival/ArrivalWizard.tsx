import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useId, useRef, useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { I18nProvider } from "../../../i18n/provider/I18nProvider";
import { ApiError } from "../../../state/regions";
import { FeaturesPicker } from "./FeaturesPicker";
import { ALL_FEATURES, applySelection, FEATURES, type Selection, toggle } from "./features";
import { ImportArchive } from "./ImportArchive";
import "./arrival.css";

/**
 * Issue 246 — the arrival wizard: what a new portal shows before anyone has an account. In the visitor's
 * language (chosen first, read from the public catalogs), it asks how the portal is installed (from scratch,
 * or another Portalab brought in from its backup — issue 247), which features to keep, then the administrator's account,
 * and shows it all before creating anything. Creating runs the first run (the account, the language), signs
 * the administrator in, applies the features and opens the setup assistant for the rest (identity, services,
 * members and their accounts…). Nothing is written before the last step; once the portal is set up the
 * wizard answers nothing more.
 */
type Step = "welcome" | "features" | "admin" | "recap" | "import";
const NEW: readonly Step[] = ["welcome", "features", "admin", "recap"];
const IMPORT: readonly Step[] = ["welcome", "import"]; // issue 247: another Portalab brought in
// what the setup assistant goes on with once the account exists (shown so the whole way is known)
const LATER = ["services", "members", "identity"] as const;

interface Account {
  login: string;
  password: string;
  displayName: string;
  email: string;
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

export function ArrivalWizard() {
  const languages = useQuery({
    queryKey: ["i18n", "public-languages"],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/i18n/public/languages" as never)).data as unknown as Languages,
  });
  const [language, setLanguage] = useState<string | null>(null);
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
  const ids = { title: useId(), language: useId(), login: useId(), password: useId(), hint: useId() };
  const ids2 = { name: useId(), email: useId() };
  const [step, setStep] = useState<Step>("welcome");
  const [install, setInstall] = useState<"new" | "import">("new");
  const [features, setFeatures] = useState<Selection>(ALL_FEATURES);
  const [account, setAccount] = useState<Account>({ login: "", password: "", displayName: "", email: "" });
  const [phase, setPhase] = useState<"account" | "signIn" | "features" | null>(null);
  const created = useRef(false); // tried again after the account exists: only what is left
  const status = useQuery({
    queryKey: ["admin", "first-run"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/admin/first-run")).data as unknown as { completed: boolean },
  });
  const create = useMutation({
    mutationFn: async () => {
      setPhase("account");
      if (!created.current)
        await api.POST("/api/v1/admin/first-run", {
          body: {
            login: account.login,
            password: account.password,
            display_name: account.displayName || null,
            email: account.email || null,
            settings: {
              "i18n.defaultLanguage": language,
              "admin.setup.progress": { install: "new", step: "services", done: ["account", "features"] },
            },
            steps: {},
          } as never,
        });
      created.current = true;
      setPhase("signIn");
      await api.POST("/api/v1/auth/login", { body: { login: account.login, password: account.password } });
      setPhase("features");
      await applySelection(features).catch(() => undefined); // the setup assistant shows them again
    },
    onSuccess: () => globalThis.location.assign("/admin/setup"),
  });

  if (status.isPending) return <FunctionalState state="loading" detail={t("account:arrival.title")} />;
  // 028: a portal already set up answers nothing to a visitor (an error, read as closed)
  if (status.data?.completed || status.isError) {
    return (
      <Shell>
        <section className="arrival__panel" role="status">
          <h2>{t("account:arrival.closed")}</h2>
          <p>
            <a className="ds-button ds-button--primary" href="/">
              {t("account:arrival.signIn")}
            </a>
          </p>
        </section>
      </Shell>
    );
  }

  const STEPS = install === "import" ? IMPORT : NEW;
  const index = STEPS.indexOf(step);
  const go = (to: Step | undefined) => to && setStep(to);
  const next = () => go(STEPS[index + 1]);
  const back = () => go(STEPS[index - 1]);
  const submitAccount = (event: FormEvent) => {
    event.preventDefault();
    next();
  };
  const set = (field: keyof Account) => (value: string) => setAccount((a) => ({ ...a, [field]: value }));
  const chosenFeatures = FEATURES.filter((f) => features.has(f.key));
  const error =
    create.error instanceof ApiError
      ? create.error.message
      : create.isError
        ? t("account:arrival.error")
        : null;

  return (
    <Shell>
      <ol className="arrival__steps" aria-label={t("account:arrival.steps")}>
        {STEPS.map((s, position) => (
          <li key={s} aria-current={s === step ? "step" : undefined}>
            <span aria-hidden="true">{position + 1}</span>
            {t(`account:arrival.step.${s}`)}
          </li>
        ))}
        {install === "new"
          ? LATER.map((s, position) => (
              <li key={s} data-later title={t("account:arrival.later")}>
                <span aria-hidden="true">{STEPS.length + position + 1}</span>
                {t(`account:arrival.step.${s}`)}
              </li>
            ))
          : null}
      </ol>
      <section className="arrival__panel" aria-labelledby={ids.title}>
        {step === "welcome" ? (
          <>
            <h2 id={ids.title}>{t("account:arrival.welcome.title")}</h2>
            <p className="arrival__lead">{t("account:arrival.welcome.lead")}</p>
            <div className="arrival__form">
              <label htmlFor={ids.language}>{t("account:arrival.welcome.language")}</label>
              <select id={ids.language} value={language} onChange={(e) => onLanguage(e.target.value)}>
                {(languages?.items ?? [{ code: language, name_native: language }]).map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name_native}
                  </option>
                ))}
              </select>
            </div>
            <h3>{t("account:arrival.welcome.install")}</h3>
            <div className="arrival__choices">
              <button
                type="button"
                className="arrival__choice"
                aria-pressed={install === "new"}
                onClick={() => setInstall("new")}
              >
                <strong>
                  <Icon name="sparkles" size={18} />
                  {t("account:arrival.install.new")}
                </strong>
                <span>{t("account:arrival.install.newHint")}</span>
              </button>
              <button
                type="button"
                className="arrival__choice"
                aria-pressed={install === "import"}
                onClick={() => setInstall("import")}
              >
                <strong>
                  <Icon name="download" size={18} />
                  {t("account:arrival.install.import")}
                </strong>
                <span>{t("account:arrival.install.importHint")}</span>
              </button>
            </div>
          </>
        ) : null}
        {step === "import" ? (
          <>
            <h2 id={ids.title}>{t("account:arrival.import.title")}</h2>
            <p className="arrival__lead">{t("account:arrival.import.lead")}</p>
            <ImportArchive language={language} />
          </>
        ) : null}
        {step === "features" ? (
          <>
            <h2 id={ids.title}>{t("account:arrival.features.title")}</h2>
            <p className="arrival__lead">{t("account:arrival.features.lead")}</p>
            <FeaturesPicker
              selection={features}
              onChange={(key, on) => setFeatures((current) => toggle(current, key, on))}
            />
          </>
        ) : null}
        {step === "admin" ? (
          <form id="arrival-admin" className="arrival__form" onSubmit={submitAccount}>
            <h2 id={ids.title}>{t("account:arrival.admin.title")}</h2>
            <p className="arrival__lead">{t("account:arrival.admin.lead")}</p>
            <label htmlFor={ids.login}>{t("account:arrival.admin.login")}</label>
            <input
              id={ids.login}
              required
              minLength={3}
              autoComplete="username"
              value={account.login}
              onChange={(e) => set("login")(e.target.value.toLowerCase())}
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
              onChange={(e) => set("password")(e.target.value)}
            />
            <p id={ids.hint} className="field-hint">
              {t("account:arrival.admin.passwordHint")}
            </p>
            <label htmlFor={ids2.name}>{t("account:arrival.admin.displayName")}</label>
            <input
              id={ids2.name}
              autoComplete="name"
              value={account.displayName}
              onChange={(e) => set("displayName")(e.target.value)}
            />
            <label htmlFor={ids2.email}>{t("account:arrival.admin.email")}</label>
            <input
              id={ids2.email}
              type="email"
              autoComplete="email"
              value={account.email}
              onChange={(e) => set("email")(e.target.value)}
            />
          </form>
        ) : null}
        {step === "recap" ? (
          <>
            <h2 id={ids.title}>{t("account:arrival.recap.title")}</h2>
            <p className="arrival__lead">{t("account:arrival.recap.lead")}</p>
            <dl className="arrival__recap">
              <div>
                <dt>{t("account:arrival.recap.install")}</dt>
                <dd>{t("account:arrival.install.new")}</dd>
              </div>
              <div>
                <dt>{t("account:arrival.welcome.language")}</dt>
                <dd>{languages?.items.find((l) => l.code === language)?.name_native ?? language}</dd>
              </div>
              <div>
                <dt>{t("account:arrival.recap.admin")}</dt>
                <dd>
                  {account.displayName || account.login} (@{account.login})
                </dd>
              </div>
              <div>
                <dt>{t("account:arrival.recap.features", { count: chosenFeatures.length })}</dt>
                <dd>{chosenFeatures.map((f) => t(`account:features.${f.key}.title`)).join(", ")}</dd>
              </div>
            </dl>
            <p className="arrival__lead">{t("account:arrival.recap.next")}</p>
            {create.isPending && phase ? <p role="status">{t(`account:arrival.phase.${phase}`)}</p> : null}
            {error ? <p role="alert">{error}</p> : null}
          </>
        ) : null}
        <footer className="arrival__actions">
          {index > 0 ? (
            <Button variant="ghost" onClick={back} disabled={create.isPending}>
              <Icon name="back" size={16} />
              {t("account:arrival.previous")}
            </Button>
          ) : (
            <span />
          )}
          {step === "admin" ? (
            <Button type="submit" form="arrival-admin">
              {t("account:arrival.next")}
              <Icon name="chevron-right" size={16} />
            </Button>
          ) : step === "recap" ? (
            <Button onClick={() => create.mutate()} disabled={create.isPending} aria-busy={create.isPending}>
              <Icon name="rocket" size={16} />
              {t("account:arrival.create")}
            </Button>
          ) : step === "import" ? (
            <span />
          ) : (
            <Button onClick={next}>
              {t("account:arrival.next")}
              <Icon name="chevron-right" size={16} />
            </Button>
          )}
        </footer>
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const t = useT();
  return (
    <main className="arrival">
      <header className="arrival__brand">
        <span className="ds-auth__mark" aria-hidden="true">
          <Icon name="sparkles" size={26} />
        </span>
        <div>
          <h1>{t("account:arrival.title")}</h1>
          <p>{t("account:arrival.subtitle")}</p>
        </div>
      </header>
      {children}
    </main>
  );
}

export default ArrivalWizard;
