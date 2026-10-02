import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

/** The caller's effective permissions — a UI hint to hide controls; the server still decides (FR-005). */
export function useMyPermissions() {
  return useQuery({
    queryKey: ["authz", "me", "permissions"],
    queryFn: async () => (await api.GET("/api/v1/me/permissions")).data ?? { permissions: [], roles: [] },
    retry: false,
  });
}

export function useHasPermission(permission: string): boolean {
  return useMyPermissions().data?.permissions.includes(permission) ?? false;
}
