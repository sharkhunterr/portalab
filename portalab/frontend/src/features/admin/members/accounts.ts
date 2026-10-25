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

/** Issue 246: a login the portal accepts (lowercase letters, digits, « . _ - », 3 to 64), from an account. */
export function loginFrom(account: ServiceAccount, taken: ReadonlySet<string>): string {
  const source =
    account.username || account.display_name || account.email?.split("@")[0] || account.external_id;
  let base = source
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^[^a-z0-9]+|[-.]+$/g, "")
    .slice(0, 56);
  if (base.length < 3)
    base = `${base || "member"}-${account.external_id}`.replace(/[^a-z0-9._-]/g, "").slice(0, 56);
  let login = base;
  for (let n = 2; taken.has(login); n++) login = `${base}-${n}`;
  return login;
}

export interface CreatedMember {
  account: ServiceAccount;
  service: string;
  login?: string;
  token?: string;
  error?: string;
}

/** Issue 246: a member made from each account (its name, its e-mail when it has one), then linked to it so its
 * past plays and requests are theirs; the member activates the account from the link (sent by e-mail when the
 * portal sends e-mails). A login already taken gets a number. */
export async function createMembers(
  items: ReadonlyArray<{ service: string; account: ServiceAccount }>,
  members: readonly AccountMember[],
): Promise<CreatedMember[]> {
  const taken = new Set(members.map((m) => m.login ?? "").filter(Boolean));
  const out: CreatedMember[] = [];
  for (const { service, account } of items) {
    let created: CreatedMember = { account, service };
    for (let attempt = 0; attempt < 5; attempt++) {
      const login = loginFrom(account, taken);
      taken.add(login);
      try {
        const { data } = await api.POST("/api/v1/users", {
          body: {
            login,
            display_name: (account.display_name || account.username || login).slice(0, 64),
            email: account.email || null,
          },
        });
        const issued = data as unknown as { user_id: string; verification_token: string };
        await api.PUT("/api/v1/admin/media/accounts/{service_id}", {
          params: { path: { service_id: service } },
          body: { external_user_id: account.external_id, user_id: issued.user_id },
        });
        created = { account, service, login, token: issued.verification_token };
        break;
      } catch (error) {
        const { status, code } = error as { status?: number; code?: string };
        created = { account, service, error: (error as Error).message };
        if (status !== 409 || !code?.includes("login")) break; // a login taken: try the next number
      }
    }
    out.push(created);
  }
  return out;
}
