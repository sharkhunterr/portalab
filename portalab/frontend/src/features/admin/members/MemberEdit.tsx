import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../../api/client";
import { AdminSection, FormActions, FormGrid, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { passwordRuleMessage } from "../../auth/passwordRules";
import { useMe } from "../../auth/useAuth";
import { ACCOUNTS_KEY, accountLabel, useServiceAccounts } from "./accounts";

/**
 * Edit a member (027, Members & access): display name and e-mail, the roles they hold (the base User role
 * is implicit and the Admin role moves only by transfer), and the service accounts linked to them —
 * unlink one here, link more from the « Service accounts » tab. Each part is exported on its own so the
 * member card (``MemberCard``) shows them inline, in a page rather than a dialog.
 */
export interface EditableMember {
  id: string;
  login: string | null;
  display_name: string | null;
  email?: string | null | undefined;
}

interface Role {
  id: string;
  key: string;
  name: string;
}

const FIXED_ROLES = new Set(["user", "admin"]);

export function MemberProfileForm({ member, onSaved }: { member: EditableMember; onSaved: () => void }) {
  const t = useT();
  const [name, setName] = useState(member.display_name ?? "");
  const [email, setEmail] = useState(member.email ?? "");
  const save = useMutation({
    mutationFn: async () => {
      await api.PATCH("/api/v1/users/{user_id}", {
        params: { path: { user_id: member.id } },
        body: { display_name: name.trim() || null, email: email.trim() },
      });
    },
    onSuccess: onSaved,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <form onSubmit={submit} className="admin-form">
      <FormGrid>
        <TextField label={t("admin:members.login")} value={member.login ?? ""} readOnly disabled />
        <TextField
          label={t("admin:members.name")}
          required
          maxLength={64}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          label={t("admin:members.email")}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </FormGrid>
      {save.isSuccess ? (
        <p role="status" className="services-admin__ok">
          {t("admin:members.saved")}
        </p>
      ) : null}
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {save.error instanceof ApiError ? save.error.message : t("admin:members.refused")}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={save.isPending}>
          <Icon name="check" size={16} />
          {t("admin:members.save")}
        </Button>
      </FormActions>
    </form>
  );
}

/** Issue 348: what a refused password says — the administrator's own password, the policy, the account. */
function passwordProblem(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof ApiError) {
    if (error.code === "identity.password_current_wrong") return t("admin:members.password.wrong");
    if (error.code === "identity.password_not_local") return t("admin:members.password.notLocal");
    if (error.code === "admin.sole_admin_protected") return t("admin:members.password.adminOnly");
    const rule = passwordRuleMessage(error, t);
    if (rule) return rule;
    if (error.code === "auth.throttled")
      return t("account:signInPhrase.throttled", {
        minutes: Math.max(1, Math.ceil(Number(error.extensions.retry_after_seconds ?? 60) / 60)),
      });
    return error.message;
  }
  return t("admin:members.refused");
}

/** Issue 348: set a member's password (forgotten, or to see the portal as they do), confirmed with the
 * administrator's own; every session of the member is signed out. Not on the administrator's own card. */
export function MemberPassword({ member }: { member: EditableMember }) {
  const t = useT();
  const me = useMe();
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [own, setOwn] = useState("");
  const mismatch = again.length > 0 && next !== again;
  const save = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/users/{user_id}/password", {
          params: { path: { user_id: member.id } },
          body: { password: own, new_password: next },
        })
      ).data,
    onSuccess: () => {
      setNext("");
      setAgain("");
      setOwn("");
    },
  });
  if (me.data?.id === member.id) return null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!mismatch) save.mutate();
  };
  return (
    <AdminSection
      title={t("admin:members.password.title")}
      icon="key"
      description={t("admin:members.password.hint")}
    >
      <form onSubmit={submit} className="admin-form">
        <FormGrid>
          <TextField
            label={t("account:signInPhrase.new")}
            type="password"
            autoComplete="new-password"
            required
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <TextField
            label={t("account:signInPhrase.again")}
            type="password"
            autoComplete="new-password"
            required
            value={again}
            error={mismatch ? t("account:signInPhrase.mismatch") : undefined}
            onChange={(e) => setAgain(e.target.value)}
          />
          <TextField
            label={t("admin:members.password.yours")}
            type="password"
            autoComplete="current-password"
            required
            value={own}
            onChange={(e) => setOwn(e.target.value)}
          />
        </FormGrid>
        {save.isSuccess ? (
          <p role="status" className="services-admin__ok">
            {t("admin:members.password.done", { count: save.data?.sessions_signed_out ?? 0 })}
          </p>
        ) : null}
        {save.isError ? (
          <p role="alert" className="services-admin__ko">
            {passwordProblem(save.error, t)}
          </p>
        ) : null}
        <FormActions>
          <Button type="submit" disabled={save.isPending || !next || !again || !own || mismatch}>
            <Icon name="key" size={16} />
            {t("admin:members.password.submit")}
          </Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}

/** Issue 408: turn a member's two-step verification off (a lost phone and no recovery code left), confirmed
 * with the administrator's own password. Not on the administrator's own card, never the Admin's. */
export function MemberTwoFactor({ member }: { member: EditableMember }) {
  const t = useT();
  const me = useMe();
  const [own, setOwn] = useState("");
  const lift = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/users/{user_id}/mfa/off", {
        params: { path: { user_id: member.id } },
        body: { password: own },
      });
    },
    onSuccess: () => setOwn(""),
  });
  if (me.data?.id === member.id) return null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    lift.mutate();
  };
  const refused =
    lift.error instanceof ApiError && lift.error.code === "admin.sole_admin_protected"
      ? t("admin:members.mfa.adminOnly")
      : passwordProblem(lift.error, t);
  return (
    <AdminSection
      title={t("admin:members.mfa.title")}
      icon="shield"
      description={t("admin:members.mfa.hint")}
    >
      <form onSubmit={submit} className="admin-form">
        <FormGrid>
          <TextField
            label={t("admin:members.password.yours")}
            type="password"
            autoComplete="current-password"
            required
            value={own}
            onChange={(e) => setOwn(e.target.value)}
          />
        </FormGrid>
        {lift.isSuccess ? (
          <p role="status" className="services-admin__ok">
            {t("admin:members.mfa.done")}
          </p>
        ) : null}
        {lift.isError ? (
          <p role="alert" className="services-admin__ko">
            {refused}
          </p>
        ) : null}
        <FormActions>
          <Button type="submit" variant="danger" disabled={lift.isPending || !own}>
            <Icon name="shield" size={16} />
            {t("admin:members.mfa.submit")}
          </Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}

export function MemberRoles({ member }: { member: EditableMember }) {
  const t = useT();
  const client = useQueryClient();
  const key = ["admin", "members", member.id, "roles"];
  const roles = useQuery({
    queryKey: ["admin", "roles"],
    retry: false,
    queryFn: async () => ((await api.GET("/api/v1/roles")).data ?? []) as Role[],
  });
  const held = useQuery({
    queryKey: key,
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/users/{user_id}/roles", { params: { path: { user_id: member.id } } })).data ??
        []) as Role[],
  });
  const toggle = useMutation({
    mutationFn: async ({ role, on }: { role: string; on: boolean }) => {
      const path = { user_id: member.id };
      if (on) await api.POST("/api/v1/users/{user_id}/roles", { params: { path }, body: { role_key: role } });
      else
        await api.DELETE("/api/v1/users/{user_id}/roles/{role_key}", {
          params: { path: { ...path, role_key: role } },
        });
    },
    onSettled: () => void client.invalidateQueries({ queryKey: key }),
  });
  if (roles.isError || held.isError) return null;
  const holds = new Set((held.data ?? []).map((r) => r.key));
  const editable = (roles.data ?? []).filter((r) => !FIXED_ROLES.has(r.key));
  return (
    <AdminSection title={t("admin:members.roles")} description={t("admin:members.rolesHint")} icon="key">
      {holds.has("admin") ? <StatusBadge tone="info">{t("admin:members.isAdmin")}</StatusBadge> : null}
      {editable.length ? (
        <div className="member-roles">
          {editable.map((role) => (
            <CheckboxField
              key={role.key}
              label={role.name}
              checked={holds.has(role.key)}
              disabled={toggle.isPending || held.isPending}
              onChange={(e) => toggle.mutate({ role: role.key, on: e.target.checked })}
            />
          ))}
        </div>
      ) : (
        <p className="admin-muted">{t("admin:members.noRoles")}</p>
      )}
      {toggle.isError ? (
        <p role="alert" className="services-admin__ko">
          {toggle.error instanceof ApiError ? toggle.error.message : t("admin:members.refused")}
        </p>
      ) : null}
    </AdminSection>
  );
}

function LinkedAccounts({ member }: { member: EditableMember }) {
  const t = useT();
  const client = useQueryClient();
  const overview = useServiceAccounts();
  const unlink = useMutation({
    mutationFn: async ({ service, account }: { service: string; account: string }) =>
      api.PUT("/api/v1/admin/media/accounts/{service_id}", {
        params: { path: { service_id: service } },
        body: { external_user_id: account, user_id: null },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ACCOUNTS_KEY }),
  });
  if (overview.isError || !overview.data) return null;
  const linked = overview.data.services.flatMap((s) =>
    s.accounts.filter((a) => a.linked_user_id === member.id).map((a) => ({ service: s, account: a })),
  );
  const suggested = overview.data.services.flatMap((s) =>
    s.accounts
      .filter((a) => !a.linked_user_id && a.suggestion?.user_id === member.id)
      .map((a) => ({ service: s, account: a })),
  );
  return (
    <AdminSection
      title={t("admin:members.linkedAccounts")}
      description={t("admin:members.linkedHint")}
      icon="link"
      flush
    >
      {linked.length ? (
        <ul className="admin-list">
          {linked.map(({ service, account }) => (
            <li key={`${service.service_id}-${account.external_id}`}>
              <span className="admin-list__main">
                <strong>{service.name}</strong>
                <span className="admin-muted">{accountLabel(account)}</span>
              </span>
              <Button
                variant="ghost"
                disabled={unlink.isPending}
                onClick={() => unlink.mutate({ service: service.service_id, account: account.external_id })}
                aria-label={`${t("admin:accounts.unlink")} ${service.name} — ${accountLabel(account)}`}
              >
                {t("admin:accounts.unlink")}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="admin-muted admin-pad">{t("admin:members.noLinked")}</p>
      )}
      {suggested.length ? (
        <p className="admin-muted admin-pad">
          {t("admin:members.suggestedHere", { count: suggested.length })}{" "}
          {suggested.map(({ service, account }) => `${service.name} : ${accountLabel(account)}`).join(", ")}
        </p>
      ) : null}
    </AdminSection>
  );
}

export function MemberEdit({ member }: { member: EditableMember }) {
  const client = useQueryClient();
  return (
    <div className="admin-dialog-body member-edit">
      <MemberProfileForm
        member={member}
        onSaved={() => void client.invalidateQueries({ queryKey: ["admin", "members"] })}
      />
      <MemberRoles member={member} />
      <LinkedAccounts member={member} />
    </div>
  );
}
