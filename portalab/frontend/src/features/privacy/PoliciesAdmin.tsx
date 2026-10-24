import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import {
  AdminPage,
  AdminSection,
  AdminTable,
  FormActions,
  FormGrid,
  StatusBadge,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { ApiError, DataRegion } from "../../state/regions";
import { type LevelKey, privacyStrings, usePrivacyStrings } from "./strings";

type Policy = components["schemas"]["PolicyOut"];
type Mode = keyof typeof privacyStrings.modes;
const POLICIES_KEY = ["privacy", "policies"] as const;

function errorText(error: unknown, t = privacyStrings): string {
  if (error instanceof ApiError && error.code === "privacy.policy_exists") return t.alreadyActive;
  return t.genericError;
}

function NewPolicy() {
  const t = usePrivacyStrings();
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
    <AdminSection title={t.newPolicyTitle} icon="plus">
      <form onSubmit={submit} className="admin-form">
        {mutation.isError ? <p role="alert">{errorText(mutation.error, t)}</p> : null}
        <FormGrid>
          <TextField
            id={ids.datum}
            label={t.datumField}
            required
            value={datum}
            onChange={(e) => setDatum(e.target.value)}
          />
          <SelectField
            id={ids.mode}
            label={t.modeField}
            value={mode}
            onChange={(e) => setMode(e.target.value as Mode)}
          >
            {(Object.keys(t.modes) as Mode[]).map((key) => (
              <option key={key} value={key}>
                {t.modes[key]}
              </option>
            ))}
          </SelectField>
          {mode === "force_visible" ? (
            <SelectField
              id={ids.level}
              label={t.levelField}
              value={level}
              onChange={(e) => setLevel(e.target.value as LevelKey)}
            >
              {(["public", "community", "leaderboard"] as LevelKey[]).map((key) => (
                <option key={key} value={key}>
                  {t.levels[key]}
                </option>
              ))}
            </SelectField>
          ) : null}
          <TextField
            id={ids.subject}
            label={t.subjectField}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />
          <TextField
            id={ids.reason}
            label={t.reasonField}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </FormGrid>
        <FormActions>
          <Button type="submit" disabled={mutation.isPending}>
            {t.apply}
          </Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}

/** Admin visibility overrides (spec 021 US2): preference preserved, restored on removal. */
export function PoliciesAdmin() {
  const t = usePrivacyStrings();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: async (id: string) => {
      await api.DELETE("/api/v1/privacy/policies/{policy_id}", { params: { path: { policy_id: id } } });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: POLICIES_KEY }),
  });
  return (
    <AdminPage icon="lock" title={t.policiesTitle} description={t.policiesDescription}>
      <AdminSection title={t.activePolicies} icon="shield" flush>
        <DataRegion<Policy[]>
          label={t.activePolicies}
          queryKey={POLICIES_KEY}
          queryFn={async () => (await api.GET("/api/v1/privacy/policies")).data ?? []}
        >
          {(policies) => (
            <AdminTable<Policy>
              label={t.activePolicies}
              rows={policies}
              rowKey={(policy) => policy.id}
              empty={<p className="admin-muted admin-pad">{t.noPolicies}</p>}
              columns={[
                {
                  key: "who",
                  header: t.datumField,
                  primary: true,
                  render: (policy) => t.policyFor(policy.subject_user_id ?? t.everyone, policy.datum_class),
                },
                {
                  key: "mode",
                  header: t.modeField,
                  render: (policy) => (
                    <StatusBadge tone={policy.mode === "force_private" ? "warn" : "info"}>
                      {t.modes[policy.mode as Mode] ?? policy.mode}
                      {policy.level ? ` (${t.levels[policy.level as LevelKey] ?? policy.level})` : ""}
                    </StatusBadge>
                  ),
                },
              ]}
              actions={(policy) => (
                <Button variant="ghost" onClick={() => remove.mutate(policy.id)}>
                  {t.removePolicy}
                </Button>
              )}
            />
          )}
        </DataRegion>
      </AdminSection>
      <NewPolicy />
    </AdminPage>
  );
}
