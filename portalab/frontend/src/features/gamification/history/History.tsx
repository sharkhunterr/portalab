import { Operations } from "../admin/Operations";

/**
 * Transaction history (spec 013 T010): every grant, spend, refund, correction is its own row (append-only).
 * Issue 114: the same journal as the administration's — a real table page by page, what made each gain,
 * the balance right after it and the levels reached — over the last year.
 */
export function History() {
  return <Operations days={365} mine />;
}
