import { useInfiniteQuery } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import { FunctionalState } from "../../design-system/FunctionalState";
import { stateForError } from "../../state/regions";
import { privacyStrings as t } from "./strings";

interface AuditItem {
  seq: number;
  occurred_at: string;
  action: string;
  actor_kind: string;
  decision: string;
  result: string;
  resource_type: string | null;
  context: Record<string, unknown>;
}

function contextText(context: Record<string, unknown>): string {
  if (context.redacted === true)
    return t.auditRedacted(String((context.keys as string[] | undefined)?.join(", ")));
  return JSON.stringify(context);
}

/** Read-only audit viewer (spec 021 T021/T036); every read is audited server-side. */
export function AuditViewer() {
  const fieldId = useId();
  const titleId = useId();
  const [draft, setDraft] = useState("");
  const [action, setAction] = useState("");
  const query = useInfiniteQuery({
    queryKey: ["audit", action],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      (
        await api.GET("/api/v1/audit", {
          params: { query: { action: action || null, cursor: pageParam ?? null, limit: 50 } },
        })
      ).data ?? { items: [], next_cursor: null },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setAction(draft);
  }

  const items = (query.data?.pages.flatMap((page) => page.items) ?? []) as unknown as AuditItem[];
  return (
    <section aria-labelledby={titleId} className="account-page">
      <h2 id={titleId}>{t.auditTitle}</h2>
      <form onSubmit={submit} className="auth-form">
        <label htmlFor={fieldId}>{t.auditAction}</label>
        <input id={fieldId} value={draft} onChange={(e) => setDraft(e.target.value)} />
        <button type="submit">{t.auditSearch}</button>
      </form>
      <a href={`/api/v1/audit/export${action ? `?action=${encodeURIComponent(action)}` : ""}`} download>
        {t.auditExport}
      </a>
      {query.isPending ? <FunctionalState state="loading" detail={t.auditTitle} /> : null}
      {query.isError ? <FunctionalState state={stateForError(query.error)} detail={t.auditTitle} /> : null}
      {query.isSuccess && items.length === 0 ? <p>{t.auditEmpty}</p> : null}
      {items.length > 0 ? (
        <ol>
          {items.map((item) => (
            <li key={item.seq}>
              <time dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString()}</time> ·{" "}
              {item.action} · {item.actor_kind} · {item.decision}/{item.result}
              {item.resource_type ? ` · ${item.resource_type}` : ""} — {contextText(item.context)}
            </li>
          ))}
        </ol>
      ) : null}
      {query.hasNextPage ? (
        <button type="button" onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage}>
          {t.auditMore}
        </button>
      ) : null}
    </section>
  );
}
