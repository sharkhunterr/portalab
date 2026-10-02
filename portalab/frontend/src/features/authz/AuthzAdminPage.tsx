import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { FunctionalState } from "../../design-system/FunctionalState";
import { ApiError, DataRegion, stateForError } from "../../state/regions";
import { type ScopeKind, authzStrings as t } from "./strings";

type Role = components["schemas"]["RoleOut"];
type Group = components["schemas"]["GroupOut"];
type Grant = components["schemas"]["GrantOut"];
type Permission = components["schemas"]["PermissionOut"];

const ROLES_KEY = ["authz", "roles"] as const;
const GROUPS_KEY = ["authz", "groups"] as const;
const PERMISSIONS_KEY = ["authz", "permissions"] as const;

function errorText(error: unknown): string {
  if (error instanceof ApiError && error.code === "authz.reserved_permission") return t.reservedRefused;
  return t.genericError;
}

function GrantForm({
  holder,
  permissions,
}: {
  holder: { kind: "role" | "group"; id: string };
  permissions: Permission[];
}) {
  const ids = { permission: useId(), effect: useId(), scope: useId(), ref: useId() };
  const queryClient = useQueryClient();
  const [permission, setPermission] = useState(permissions[0]?.key ?? "");
  const [effect, setEffect] = useState<"allow" | "deny">("allow");
  const [scope, setScope] = useState<ScopeKind>("global");
  const [scopeRef, setScopeRef] = useState("");
  const mutation = useMutation({
    mutationFn: async () => {
      const body = { permission_key: permission, effect, scope_kind: scope, scope_ref: scopeRef };
      if (holder.kind === "role") {
        await api.POST("/api/v1/roles/{role_id}/grants", { params: { path: { role_id: holder.id } }, body });
      } else {
        await api.POST("/api/v1/groups/{group_id}/grants", {
          params: { path: { group_id: holder.id } },
          body,
        });
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["authz", "grants", holder.id] }),
  });
  const needsRef = scope === "module" || scope === "service" || scope === "plugin";

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} className="auth-form">
      {mutation.isError ? <p role="alert">{errorText(mutation.error)}</p> : null}
      <label htmlFor={ids.permission}>{t.permissionField}</label>
      <select id={ids.permission} value={permission} onChange={(event) => setPermission(event.target.value)}>
        {permissions.map((item) => (
          <option key={item.key} value={item.key}>
            {item.key}
            {item.reserved ? ` — ${t.reserved}` : ""}
            {item.sensitive ? ` — ${t.sensitive}` : ""}
          </option>
        ))}
      </select>
      <label htmlFor={ids.effect}>{t.effectField}</label>
      <select
        id={ids.effect}
        value={effect}
        onChange={(event) => setEffect(event.target.value as "allow" | "deny")}
      >
        <option value="allow">{t.effects.allow}</option>
        <option value="deny">{t.effects.deny}</option>
      </select>
      <label htmlFor={ids.scope}>{t.scopeField}</label>
      <select id={ids.scope} value={scope} onChange={(event) => setScope(event.target.value as ScopeKind)}>
        {(Object.keys(t.scopes) as ScopeKind[]).map((key) => (
          <option key={key} value={key}>
            {t.scopes[key]}
          </option>
        ))}
      </select>
      {needsRef ? (
        <>
          <label htmlFor={ids.ref}>{t.scopeRefField}</label>
          <input
            id={ids.ref}
            required
            value={scopeRef}
            onChange={(event) => setScopeRef(event.target.value)}
          />
        </>
      ) : null}
      <button type="submit" disabled={mutation.isPending || !permission} aria-busy={mutation.isPending}>
        {t.addGrant}
      </button>
    </form>
  );
}

function GrantList({ holder, name }: { holder: { kind: "role" | "group"; id: string }; name: string }) {
  const titleId = useId();
  const queryClient = useQueryClient();
  const permissions = useQuery({
    queryKey: PERMISSIONS_KEY,
    queryFn: async () => (await api.GET("/api/v1/permissions")).data ?? [],
  });
  const remove = useMutation({
    mutationFn: async (grantId: string) => {
      await api.DELETE("/api/v1/grants/{grant_id}", { params: { path: { grant_id: grantId } } });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["authz", "grants", holder.id] }),
  });
  return (
    <div className="grant-list">
      <h3 id={titleId}>{t.grantsTitle(name)}</h3>
      <DataRegion<Grant[]>
        label={t.grantsTitle(name)}
        queryKey={["authz", "grants", holder.id]}
        queryFn={async () =>
          holder.kind === "role"
            ? ((await api.GET("/api/v1/roles/{role_id}/grants", { params: { path: { role_id: holder.id } } }))
                .data ?? [])
            : ((
                await api.GET("/api/v1/groups/{group_id}/grants", {
                  params: { path: { group_id: holder.id } },
                })
              ).data ?? [])
        }
      >
        {(grants) =>
          grants.length === 0 ? (
            <p>{t.noGrants}</p>
          ) : (
            <ul>
              {grants.map((grant) => (
                <li key={grant.id}>
                  <span>
                    {grant.effect === "deny" ? `${t.effects.deny}: ` : ""}
                    {grant.permission_key} · {t.scopes[grant.scope_kind as ScopeKind] ?? grant.scope_kind}
                    {grant.scope_ref ? ` (${grant.scope_ref})` : ""}
                  </span>{" "}
                  <button type="button" onClick={() => remove.mutate(grant.id)}>
                    {t.removeGrant(grant.permission_key)}
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </DataRegion>
      {permissions.data ? <GrantForm holder={holder} permissions={permissions.data} /> : null}
      {permissions.isError ? <FunctionalState state={stateForError(permissions.error)} /> : null}
    </div>
  );
}

function CreateForm({ kind }: { kind: "role" | "group" }) {
  const ids = { key: useId(), name: useId(), title: useId() };
  const queryClient = useQueryClient();
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const mutation = useMutation({
    mutationFn: async () => {
      if (kind === "role") await api.POST("/api/v1/roles", { body: { key, name } });
      else await api.POST("/api/v1/groups", { body: { key, name, description: "" } });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: kind === "role" ? ROLES_KEY : GROUPS_KEY }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} aria-labelledby={ids.title} className="auth-form">
      <h3 id={ids.title}>{kind === "role" ? t.newRoleTitle : t.newGroupTitle}</h3>
      {mutation.isError ? <p role="alert">{errorText(mutation.error)}</p> : null}
      <label htmlFor={ids.key}>{t.keyField}</label>
      <input
        id={ids.key}
        required
        pattern="[a-z][a-z0-9_-]+"
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <label htmlFor={ids.name}>{t.nameField}</label>
      <input id={ids.name} required value={name} onChange={(e) => setName(e.target.value)} />
      <button type="submit" disabled={mutation.isPending}>
        {t.create}
      </button>
    </form>
  );
}

/** Roles, groups and their grants (spec 003 US2/US6). Admin-only on the server (`users.roles.manage`). */
export function AuthzAdminPage() {
  const [selected, setSelected] = useState<{ kind: "role" | "group"; id: string; name: string } | null>(null);
  return (
    <div className="account-page">
      <h1>{t.title}</h1>
      <div className="authz-roles">
        <h2>{t.rolesTitle}</h2>
        <DataRegion<Role[]>
          label={t.rolesTitle}
          queryKey={ROLES_KEY}
          queryFn={async () => (await api.GET("/api/v1/roles")).data ?? []}
        >
          {(roles) => (
            <ul>
              {roles.map((role) => (
                <li key={role.id}>
                  <button
                    type="button"
                    onClick={() => setSelected({ kind: "role", id: role.id, name: role.name })}
                  >
                    {t.manage(role.name)}
                  </button>
                  {role.system ? ` · ${t.base}` : ""}
                </li>
              ))}
            </ul>
          )}
        </DataRegion>
        <CreateForm kind="role" />
      </div>
      <div className="authz-groups">
        <h2>{t.groupsTitle}</h2>
        <DataRegion<Group[]>
          label={t.groupsTitle}
          queryKey={GROUPS_KEY}
          queryFn={async () => (await api.GET("/api/v1/groups")).data ?? []}
        >
          {(groups) => (
            <ul>
              {groups.map((group) => (
                <li key={group.id}>
                  <button
                    type="button"
                    onClick={() => setSelected({ kind: "group", id: group.id, name: group.name })}
                  >
                    {t.manage(group.name)}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </DataRegion>
        <CreateForm kind="group" />
      </div>
      {selected ? <GrantList holder={{ kind: selected.kind, id: selected.id }} name={selected.name} /> : null}
    </div>
  );
}
