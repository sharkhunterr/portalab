import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import {
  AdminGrid,
  AdminPage,
  AdminSection,
  AdminTable,
  FormActions,
  FormGrid,
  StatusBadge,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
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
    <form onSubmit={submit} className="admin-form">
      {mutation.isError ? <p role="alert">{errorText(mutation.error)}</p> : null}
      <FormGrid>
        <SelectField
          id={ids.permission}
          label={t.permissionField}
          value={permission}
          onChange={(event) => setPermission(event.target.value)}
        >
          {permissions.map((item) => (
            <option key={item.key} value={item.key}>
              {item.key}
              {item.reserved ? ` — ${t.reserved}` : ""}
              {item.sensitive ? ` — ${t.sensitive}` : ""}
            </option>
          ))}
        </SelectField>
        <SelectField
          id={ids.effect}
          label={t.effectField}
          value={effect}
          onChange={(event) => setEffect(event.target.value as "allow" | "deny")}
        >
          <option value="allow">{t.effects.allow}</option>
          <option value="deny">{t.effects.deny}</option>
        </SelectField>
        <SelectField
          id={ids.scope}
          label={t.scopeField}
          value={scope}
          onChange={(event) => setScope(event.target.value as ScopeKind)}
        >
          {(Object.keys(t.scopes) as ScopeKind[]).map((key) => (
            <option key={key} value={key}>
              {t.scopes[key]}
            </option>
          ))}
        </SelectField>
        {needsRef ? (
          <TextField
            id={ids.ref}
            label={t.scopeRefField}
            required
            value={scopeRef}
            onChange={(event) => setScopeRef(event.target.value)}
          />
        ) : null}
      </FormGrid>
      <FormActions>
        <Button type="submit" disabled={mutation.isPending || !permission} aria-busy={mutation.isPending}>
          <Icon name="plus" size={16} />
          {t.addGrant}
        </Button>
      </FormActions>
    </form>
  );
}

function GrantList({ holder, name }: { holder: { kind: "role" | "group"; id: string }; name: string }) {
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
    <AdminSection title={t.grantsTitle(name)} icon="key" span="full">
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
        {(grants) => (
          <AdminTable<Grant>
            label={t.grantsTitle(name)}
            rows={grants}
            rowKey={(grant) => grant.id}
            empty={<p className="admin-muted">{t.noGrants}</p>}
            columns={[
              {
                key: "permission",
                header: t.permissionField,
                primary: true,
                render: (grant) => <code>{grant.permission_key}</code>,
              },
              {
                key: "effect",
                header: t.effectField,
                render: (grant) => (
                  <StatusBadge tone={grant.effect === "deny" ? "bad" : "ok"}>
                    {grant.effect === "deny" ? t.effects.deny : t.effects.allow}
                  </StatusBadge>
                ),
              },
              {
                key: "scope",
                header: t.scopeField,
                render: (grant) =>
                  `${t.scopes[grant.scope_kind as ScopeKind] ?? grant.scope_kind}${grant.scope_ref ? ` (${grant.scope_ref})` : ""}`,
              },
            ]}
            actions={(grant) => (
              <Button variant="ghost" onClick={() => remove.mutate(grant.id)}>
                <Icon name="trash" size={16} />
                <span className="visually-hidden">{t.removeGrant(grant.permission_key)}</span>
              </Button>
            )}
          />
        )}
      </DataRegion>
      {permissions.data ? <GrantForm holder={holder} permissions={permissions.data} /> : null}
      {permissions.isError ? <FunctionalState state={stateForError(permissions.error)} /> : null}
    </AdminSection>
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
    <form onSubmit={submit} className="admin-form">
      {mutation.isError ? <p role="alert">{errorText(mutation.error)}</p> : null}
      {mutation.isSuccess ? <p role="status">✓</p> : null}
      <FormGrid>
        <TextField
          id={ids.key}
          label={t.keyField}
          required
          pattern="[a-z][a-z0-9_-]+"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <TextField
          id={ids.name}
          label={t.nameField}
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </FormGrid>
      <FormActions>
        <Button type="submit" disabled={mutation.isPending}>
          {t.create}
        </Button>
      </FormActions>
    </form>
  );
}

function CreateButton({ kind }: { kind: "role" | "group" }) {
  return (
    <Dialog
      title={kind === "role" ? t.newRoleTitle : t.newGroupTitle}
      trigger={
        <Button variant="secondary">
          <Icon name="plus" size={16} />
          {kind === "role" ? t.newRoleTitle : t.newGroupTitle}
        </Button>
      }
    >
      <CreateForm kind={kind} />
    </Dialog>
  );
}

/** Roles, groups and their grants (spec 003 US2/US6, 027 administration kit). Admin-only on the server. */
type Holder = { kind: "role" | "group"; id: string; name: string };

function HolderList({
  items,
  label,
  selected,
  onSelect,
}: {
  items: Array<Holder & { base?: boolean }>;
  label: string;
  selected: Holder | null;
  onSelect: (holder: Holder) => void;
}) {
  return (
    <ul className="admin-list" aria-label={label}>
      {items.map((item) => (
        <li key={item.id} data-selected={selected?.id === item.id || undefined}>
          <span className="admin-list__main">
            <strong>{item.name}</strong>
            {item.base ? <span className="admin-muted">{t.base}</span> : null}
          </span>
          <Button
            variant={selected?.id === item.id ? "primary" : "ghost"}
            aria-pressed={selected?.id === item.id}
            onClick={() => onSelect(item)}
          >
            {t.manage(item.name)}
          </Button>
        </li>
      ))}
    </ul>
  );
}

export function AuthzAdminPage() {
  const [selected, setSelected] = useState<Holder | null>(null);
  return (
    <AdminPage icon="key" title={t.title} description={t.description} primary={<CreateButton kind="role" />}>
      <AdminGrid>
        <AdminSection title={t.rolesTitle} icon="shield" flush>
          <DataRegion<Role[]>
            label={t.rolesTitle}
            queryKey={ROLES_KEY}
            queryFn={async () => (await api.GET("/api/v1/roles")).data ?? []}
          >
            {(roles) => (
              <HolderList
                label={t.rolesTitle}
                selected={selected}
                onSelect={setSelected}
                items={roles.map((role) => ({
                  kind: "role",
                  id: role.id,
                  name: role.name,
                  base: role.system,
                }))}
              />
            )}
          </DataRegion>
        </AdminSection>
        <AdminSection title={t.groupsTitle} icon="users" flush actions={<CreateButton kind="group" />}>
          <DataRegion<Group[]>
            label={t.groupsTitle}
            queryKey={GROUPS_KEY}
            queryFn={async () => (await api.GET("/api/v1/groups")).data ?? []}
          >
            {(groups) =>
              groups.length ? (
                <HolderList
                  label={t.groupsTitle}
                  selected={selected}
                  onSelect={setSelected}
                  items={groups.map((group) => ({ kind: "group", id: group.id, name: group.name }))}
                />
              ) : (
                <p className="admin-muted admin-pad">{t.noGroups}</p>
              )
            }
          </DataRegion>
        </AdminSection>
        {selected ? (
          <GrantList
            key={selected.id}
            holder={{ kind: selected.kind, id: selected.id }}
            name={selected.name}
          />
        ) : (
          <AdminSection title={t.grantsPick} icon="key" span="full">
            <p className="admin-muted">{t.grantsHint}</p>
          </AdminSection>
        )}
      </AdminGrid>
    </AdminPage>
  );
}
