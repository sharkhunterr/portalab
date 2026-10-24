import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import { FunctionalState } from "../../design-system/FunctionalState";
import { ApiError } from "../../state/regions";
import { useAdminStrings } from "./strings";

interface Status {
  completed: boolean;
  steps: { step: string; skippable: boolean }[];
}

/**
 * First-run (spec 020 US4): creates the sole Admin — everything else is the setup assistant's (issue 6), which
 * the administrator finds in the Control Center once signed in.
 */
export function FirstRunWizard() {
  const t = useAdminStrings();
  const ids = { login: useId(), password: useId(), hint: useId(), name: useId(), title: useId() };
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const status = useQuery({
    queryKey: ["admin", "first-run"],
    queryFn: async () => (await api.GET("/api/v1/admin/first-run")).data as unknown as Status,
  });
  const mutation = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/admin/first-run", {
        body: { login, password, display_name: displayName || null, settings: {}, steps: {} },
      });
    },
  });

  if (status.isPending) return <FunctionalState state="loading" detail={t.wizardTitle} />;
  // 028: once the portal is set up, its first run answers nothing to a visitor (an error, read as closed)
  const closed =
    mutation.error instanceof ApiError && (mutation.error.status === 410 || mutation.error.status === 401);
  if (status.data?.completed || status.isError || closed) {
    return <p role="status">{t.closed}</p>;
  }
  if (mutation.isSuccess) {
    return (
      <div className="auth-form" role="status">
        <p>{t.finished}</p>
        <a className="ds-button ds-button--primary" href="/">
          {t.signIn}
        </a>
      </div>
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} aria-labelledby={ids.title} className="auth-form">
      <h1 id={ids.title}>{t.wizardTitle}</h1>
      <p>{t.wizardIntro}</p>
      {mutation.isError ? (
        <p role="alert">{mutation.error instanceof ApiError ? mutation.error.message : t.genericError}</p>
      ) : null}
      <label htmlFor={ids.login}>{t.loginField}</label>
      <input
        id={ids.login}
        required
        autoComplete="username"
        value={login}
        onChange={(e) => setLogin(e.target.value)}
      />
      <label htmlFor={ids.password}>{t.passwordField}</label>
      <input
        id={ids.password}
        type="password"
        required
        minLength={12}
        aria-describedby={ids.hint}
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <p id={ids.hint} className="field-hint">
        {t.passwordHint}
      </p>
      <label htmlFor={ids.name}>{t.displayNameField}</label>
      <input id={ids.name} value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
      <button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
        {t.finish}
      </button>
    </form>
  );
}
