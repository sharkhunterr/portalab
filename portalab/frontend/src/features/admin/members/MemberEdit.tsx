import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../../api/client";
import { AdminSection, FormActions, FormGrid, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
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
