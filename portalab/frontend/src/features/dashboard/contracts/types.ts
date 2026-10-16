import type { z } from "zod";

/**
 * 028 (US6, R26): a data contract the portal offers packs' widgets. The member's own page reads it through
 * the portal's usual routes (the member's session, the queries the rest of the interface already shares)
 * and hands the widget only what the contract's schema keeps — never an address, an identifier or a token.
 */
export interface SourceQuery {
  queryKey: readonly unknown[];
  queryFn: () => Promise<unknown>;
}

export interface Contract<T = unknown> {
  key: string;
  /** what the member needs to read it (the server says which contracts this member may not read) */
  permission: string;
  /** how often it is read again, in seconds */
  refreshS: number;
  /** the routes it reads, as queries shared with the rest of the interface */
  sources: SourceQuery[];
  /** the contract's fields only, from what the routes answered (in the order of ``sources``) */
  schema: z.ZodType<T>;
  shape: (answers: unknown[]) => unknown;
}

/** How many entries a list contract hands at most (a widget shows a few, never the whole library). */
export const LIST_LIMIT = 12;
