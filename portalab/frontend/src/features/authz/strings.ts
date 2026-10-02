/**
 * Authorization admin strings (spec 003 T035). Externalized for the i18n module (spec 026). The screens are
 * UI hints only: every action is authorized again by the server.
 */
export const authzStrings = {
  title: "Roles & permissions",
  rolesTitle: "Roles",
  groupsTitle: "Groups",
  grantsTitle: (name: string) => `Permissions of “${name}”`,
  noGrants: "No permission granted yet.",
  permissionField: "Permission",
  effectField: "Effect",
  effects: { allow: "Allow", deny: "Deny" },
  scopeField: "Scope",
  scopes: {
    global: "Everywhere",
    self: "Own account only",
    owned: "Own objects only",
    module: "One module",
    service: "One service",
    plugin: "One plugin",
  },
  scopeRefField: "Module, service or plugin",
  addGrant: "Add the permission",
  removeGrant: (key: string) => `Remove ${key}`,
  reserved: "Admin only",
  sensitive: "Sensitive",
  base: "Base role",
  newRoleTitle: "New role",
  newGroupTitle: "New group",
  keyField: "Key",
  nameField: "Name",
  create: "Create",
  manage: (name: string) => `Manage ${name}`,
  reservedRefused: "This permission is reserved to the Admin and cannot be granted.",
  genericError: "The change was refused. Check the values and try again.",
} as const;

export type ScopeKind = keyof typeof authzStrings.scopes;
