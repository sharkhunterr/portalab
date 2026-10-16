import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { api } from "../../api/client";
import { ApiError } from "../../state/regions";
import "../content/content.css";
import { FormMessage } from "./FormMessage";
import { authStrings as t } from "./strings";
import { useLogin } from "./useAuth";

/** Message for a failed sign-in; the server answers identically for unknown logins and wrong passwords. */
export function loginErrorMessage(error: unknown): string {
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

export function LoginForm() {
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
          {loginErrorMessage(error)}
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
    </form>
  );
}
