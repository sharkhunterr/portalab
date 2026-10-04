import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";

/** The accounts each connected service knows and the member each one belongs to (027 mapping). */
export interface ServiceAccount {
  external_id: string;
  username: string | null;
  display_name: string | null;
  email: string | null;
  linked_user_id: string | null;
  verified: boolean;
  suggestion: { user_id: string; reason: "email" | "name" } | null;
  unlinked_sessions: number;
}

export interface ServiceAccounts {
  service_id: string;
  name: string;
  connector: string;
  available: boolean;
  accounts: ServiceAccount[];
}

export interface AccountMember {
  id: string;
  login: string | null;
  display_name: string | null;
  email: string | null;
}

export interface AccountsOverview {
  services: ServiceAccounts[];
  members: AccountMember[];
}

export const ACCOUNTS_KEY = ["admin", "media", "accounts"] as const;

export function useServiceAccounts() {
  return useQuery({
    queryKey: ACCOUNTS_KEY,
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/admin/media/accounts")).data as unknown as AccountsOverview,
  });
}

export function accountLabel(account: ServiceAccount): string {
  return account.display_name || account.username || account.email || account.external_id;
}

export function memberLabel(member: AccountMember | undefined): string {
  return member ? (member.display_name ?? member.login ?? member.id) : "";
}
