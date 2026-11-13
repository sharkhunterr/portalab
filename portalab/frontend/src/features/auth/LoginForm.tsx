import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { api } from "../../api/client";
import { Dialog } from "../../design-system/components/Overlays";
import { ApiError } from "../../state/regions";
import { useSignInTerms } from "../terms/api";
import "../content/content.css";
import { FormMessage } from "./FormMessage";
import { authStrings, useAuthStrings } from "./strings";
import { isMfaRequired, useLogin, useLoginMfa } from "./useAuth";

/** Message for a failed sign-in; the server answers identically for unknown logins and wrong passwords. */
export function loginErrorMessage(error: unknown, t = authStrings): string {
  if (!(error instanceof ApiError)) return t.genericError;
  if (error.code === "auth.throttled") {
    return t.throttled(Number(error.extensions.retry_after_seconds ?? 60));
  }
  if (error.code === "auth.account_unavailable") {
    const until = error.extensions.deletion_cancellable_until;
    return typeof until === "string"
      ? t.pendingDeletion(new Date(until).toLocaleString())
      : t.accountUnavailable;
  }
  if (error.status === 503) return t.unavailable;
  return t.invalidCredentials;
}

/** 027: « Sign in with Authentik » when the single sign-on is set up; it comes back with the session. */
function SingleSignOn() {
  const t = useAuthStrings();
  const sso = useQuery({
    queryKey: ["auth", "oidc"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/auth/oidc")).data ?? { enabled: false, label: "" }) as {
        enabled: boolean;
        label: string;
      },
  });
  if (!sso.data?.enabled) return null;
  const next = new URLSearchParams(window.location.search).get("next") ?? "/";
  return (
    <div className="auth-sso">
      <a className="auth-sso__button" href={`/api/v1/auth/oidc/start?next=${encodeURIComponent(next)}`}>
        {t.ssoSignIn(sso.data.label)}
      </a>
      <p className="auth-sso__or">{t.ssoOr}</p>
    </div>
  );
}

/** Issue 157: the terms of use in force, readable before signing in — only when the administrators offer
 * them on the sign-in page (off by default: the server then answers nothing). */
function TermsLink() {
  const t = useAuthStrings();
  const terms = useSignInTerms();
  if (!terms.data) return null;
  return (
    <p className="auth-terms">
      <Dialog
        size="lg"
        title={terms.data.title}
        closeLabel={t.close}
        trigger={
          <button type="button" className="auth-terms__link">
            {t.termsLink}
          </button>
        }
      >
        <div
          className="content-body"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: server-sanitized by the single Markdown pipeline (nh3 allowlist)
          dangerouslySetInnerHTML={{ __html: terms.data.html }}
        />
      </Dialog>
    </p>
  );
}

/** Issue 408: what a refused second step says. */
export function mfaErrorMessage(error: unknown, t = authStrings): string {
  if (!(error instanceof ApiError)) return t.genericError;
  if (error.code === "auth.mfa_code_wrong") return t.mfaWrong;
  if (error.code === "auth.mfa_expired") return t.mfaExpired;
  if (error.code === "auth.throttled") return t.throttled(Number(error.extensions.retry_after_seconds ?? 60));
  return t.genericError;
}

/** Issue 408: the sign-in's second step, after a right password — the authenticator app's code. */
function SecondFactorForm({ challenge, onBack }: { challenge: string; onBack: () => void }) {
  const t = useAuthStrings();
  const codeId = useId();
  const [code, setCode] = useState("");
  const mutation = useLoginMfa();
  const messageRef = useRef<HTMLParagraphElement>(null);
  const expired = mutation.error instanceof ApiError && mutation.error.code === "auth.mfa_expired";

  useEffect(() => {
    if (mutation.error) messageRef.current?.focus();
  }, [mutation.error]);

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate({ challenge, code: code.trim() });
  }

  return (
    <form onSubmit={submit} aria-labelledby={`${codeId}-title`} className="auth-form" noValidate>
      <h1 id={`${codeId}-title`}>{t.mfaTitle}</h1>
      <p id={`${codeId}-hint`}>{t.mfaHint}</p>
      {mutation.error ? (
        <FormMessage ref={messageRef} kind="error">
          {mfaErrorMessage(mutation.error, t)}
        </FormMessage>
      ) : null}
      <label htmlFor={codeId}>{t.mfaField}</label>
      <input
        id={codeId}
        name="code"
        autoComplete="one-time-code"
        inputMode="text"
        autoCapitalize="none"
        spellCheck={false}
        maxLength={32}
        aria-describedby={`${codeId}-hint`}
        required
        // biome-ignore lint/a11y/noAutofocus: the only field of the step the user just reached
        autoFocus
        value={code}
        onChange={(event) => setCode(event.target.value)}
      />
      <button type="submit" disabled={mutation.isPending || expired || code.trim().length < 6}>
        {mutation.isPending ? t.signingIn : t.mfaSubmit}
      </button>
      <button type="button" onClick={onBack}>
        {t.mfaBack}
      </button>
    </form>
  );
}

export function LoginForm() {
  const t = useAuthStrings();
  const loginId = useId();
  const passwordId = useId();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [cancelled, setCancelled] = useState(false);
  const mutation = useLogin();
  const messageRef = useRef<HTMLParagraphElement>(null);
  const error = mutation.error;
  const pendingDeletion =
    error instanceof ApiError && typeof error.extensions.deletion_cancellable_until === "string";
  const sso = new URLSearchParams(window.location.search).get("sso"); // 027: back from a failed sign-on

  useEffect(() => {
    if (error || cancelled) messageRef.current?.focus();
  }, [error, cancelled]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setCancelled(false);
    mutation.mutate({ login, password });
  }

  if (isMfaRequired(mutation.data)) {
    return (
      <SecondFactorForm
        challenge={mutation.data.challenge}
        onBack={() => {
          mutation.reset();
          setPassword("");
        }}
      />
    );
  }

  async function cancelDeletion() {
    await api.POST("/api/v1/auth/deletion/cancel", { body: { login, password } });
    mutation.reset();
    setCancelled(true);
  }

  return (
    <form onSubmit={submit} aria-labelledby={`${loginId}-title`} className="auth-form" noValidate>
      <h1 id={`${loginId}-title`}>{t.loginTitle}</h1>
      {sso && !error ? (
        <FormMessage kind="error">{sso === "unavailable" ? t.ssoUnavailable : t.ssoFailed}</FormMessage>
      ) : null}
      <SingleSignOn />
      {error ? (
        <FormMessage ref={messageRef} kind="error">
          {loginErrorMessage(error, t)}
        </FormMessage>
      ) : null}
      {cancelled ? (
        <FormMessage ref={messageRef} kind="success">
          {t.deletionCancelled}
        </FormMessage>
      ) : null}
      <label htmlFor={loginId}>{t.loginField}</label>
      <input
        id={loginId}
        name="login"
        autoComplete="username"
        required
        value={login}
        onChange={(event) => setLogin(event.target.value)}
      />
      <label htmlFor={passwordId}>{t.passwordField}</label>
      <input
        id={passwordId}
        name="password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
        {mutation.isPending ? t.signingIn : t.signIn}
      </button>
      {pendingDeletion ? (
        <button type="button" onClick={() => void cancelDeletion()}>
          {t.cancelDeletion}
        </button>
      ) : null}
      <TermsLink />
    </form>
  );
}
