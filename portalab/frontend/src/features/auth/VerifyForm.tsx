import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { api } from "../../api/client";
import { ApiError } from "../../state/regions";
import { FormMessage } from "./FormMessage";
import { authStrings as t } from "./strings";

function verifyErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "auth.invalid_token") return t.invalidToken;
    if (error.status === 422) return error.message;
  }
  return t.genericError;
}

/** Account activation with the one-time code handed over by the Admin (CD-036) or delivered by e-mail. */
export function VerifyForm({ initialToken = "" }: { initialToken?: string }) {
  const tokenId = useId();
  const passwordId = useId();
  const hintId = useId();
  const [token, setToken] = useState(initialToken);
  const [password, setPassword] = useState("");
  const messageRef = useRef<HTMLParagraphElement>(null);
  const mutation = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/verify", { body: { token, password: password || null } });
    },
  });

  useEffect(() => {
    if (mutation.isError || mutation.isSuccess) messageRef.current?.focus();
  }, [mutation.isError, mutation.isSuccess]);

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} aria-labelledby={`${tokenId}-title`} className="auth-form" noValidate>
      <h1 id={`${tokenId}-title`}>{t.verifyTitle}</h1>
      {mutation.isError ? (
        <FormMessage ref={messageRef} kind="error">
          {verifyErrorMessage(mutation.error)}
        </FormMessage>
      ) : null}
      {mutation.isSuccess ? (
        <FormMessage ref={messageRef} kind="success">
          {t.activated}
        </FormMessage>
      ) : null}
      <label htmlFor={tokenId}>{t.tokenField}</label>
      <input
        id={tokenId}
        name="token"
        autoComplete="one-time-code"
        required
        value={token}
        onChange={(event) => setToken(event.target.value)}
      />
      <label htmlFor={passwordId}>{t.newPasswordField}</label>
      <input
        id={passwordId}
        name="new-password"
        type="password"
        autoComplete="new-password"
        aria-describedby={hintId}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <p id={hintId} className="field-hint">
        {t.newPasswordHint}
      </p>
      <button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
        {t.activate}
      </button>
    </form>
  );
}
