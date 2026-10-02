import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { ApiError, DataRegion } from "../../state/regions";
import { type LevelKey, privacyStrings as t } from "./strings";

type Policy = components["schemas"]["PolicyOut"];
type Mode = keyof typeof t.modes;
const POLICIES_KEY = ["privacy", "policies"] as const;

function errorText(error: unknown): string {
  if (error instanceof ApiError && error.code === "privacy.policy_exists") return t.alreadyActive;
  return t.genericError;
}

function NewPolicy() {
  const ids = {
    datum: useId(),
    mode: useId(),
    level: useId(),
    subject: useId(),
    reason: useId(),
    title: useId(),
  };
  const queryClient = useQueryClient();
  const [datum, setDatum] = useState("profile_field");
  const [mode, setMode] = useState<Mode>("force_private");
  const [level, setLevel] = useState<LevelKey>("community");
  const [subject, setSubject] = useState("");
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/privacy/policies", {
        body: {
          datum_class: datum,
          mode,
          level: mode === "force_visible" ? level : null,
          subject_user_id: subject || null,
          reason,
        },
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: POLICIES_KEY }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} aria-labelledby={ids.title} className="auth-form">
      <h3 id={ids.title}>{t.newPolicyTitle}</h3>
      {mutation.isError ? <p role="alert">{errorText(mutation.error)}</p> : null}
      <label htmlFor={ids.datum}>{t.datumField}</label>
      <input id={ids.datum} required value={datum} onChange={(e) => setDatum(e.target.value)} />
      <label htmlFor={ids.mode}>{t.modeField}</label>
      <select id={ids.mode} value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
        {(Object.keys(t.modes) as Mode[]).map((key) => (
          <option key={key} value={key}>
            {t.modes[key]}
          </option>
        ))}
      </select>
      {mode === "force_visible" ? (
        <>
          <label htmlFor={ids.level}>{t.levelField}</label>
          <select id={ids.level} value={level} onChange={(e) => setLevel(e.target.value as LevelKey)}>
            {(["public", "community", "leaderboard"] as LevelKey[]).map((key) => (
              <option key={key} value={key}>
                {t.levels[key]}
              </option>
            ))}
          </select>
        </>
      ) : null}
      <label htmlFor={ids.subject}>{t.subjectField}</label>
      <input id={ids.subject} value={subject} onChange={(e) => setSubject(e.target.value)} />
      <label htmlFor={ids.reason}>{t.reasonField}</label>
      <input id={ids.reason} required value={reason} onChange={(e) => setReason(e.target.value)} />
      <button type="submit" disabled={mutation.isPending}>
        {t.apply}
      </button>
    </form>
  );
}

/** Admin visibility overrides (spec 021 US2): preference preserved, restored on removal. */
export function PoliciesAdmin() {
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: async (id: string) => {
      await api.DELETE("/api/v1/privacy/policies/{policy_id}", { params: { path: { policy_id: id } } });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: POLICIES_KEY }),
  });
  return (
    <div className="account-page">
      <h2>{t.policiesTitle}</h2>
      <DataRegion<Policy[]>
        label={t.policiesTitle}
        queryKey={POLICIES_KEY}
        queryFn={async () => (await api.GET("/api/v1/privacy/policies")).data ?? []}
      >
        {(policies) =>
          policies.length === 0 ? (
            <p>{t.noPolicies}</p>
          ) : (
            <ul>
              {policies.map((policy) => (
                <li key={policy.id}>
                  {t.policyFor(policy.subject_user_id ?? t.everyone, policy.datum_class)} ·{" "}
                  {t.modes[policy.mode as Mode] ?? policy.mode}
                  {policy.level ? ` (${t.levels[policy.level as LevelKey] ?? policy.level})` : ""}{" "}
                  <button type="button" onClick={() => remove.mutate(policy.id)}>
                    {t.removePolicy}
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </DataRegion>
      <NewPolicy />
    </div>
  );
}
