import { useInfiniteQuery } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import { AdminPage, AdminSection, AdminTable, StatusBadge } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
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
  const exportHref = `/api/v1/audit/export${action ? `?action=${encodeURIComponent(action)}` : ""}`;
  return (
    <AdminPage
      icon="list"
      title={t.auditTitle}
      description={t.auditDescription}
      secondary={
        <a className="ds-button ds-button--ghost" href={exportHref} download>
          <Icon name="arrow-down" size={16} />
          {t.auditExport}
        </a>
      }
      wide
    >
      <AdminSection title={t.auditEntries} icon="list" flush>
        <form onSubmit={submit} className="audit-filter">
          <div className="ds-field audit-filter__field">
            <label htmlFor={fieldId}>{t.auditAction}</label>
            <input
              id={fieldId}
              value={draft}
              placeholder="authorize:"
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
          <Button type="submit" variant="secondary">
            <Icon name="search" size={16} />
            {t.auditSearch}
          </Button>
        </form>
        {query.isPending ? <FunctionalState state="loading" detail={t.auditTitle} /> : null}
        {query.isError ? <FunctionalState state={stateForError(query.error)} detail={t.auditTitle} /> : null}
        {query.isSuccess ? (
          <AdminTable<AuditItem>
            label={t.auditEntries}
            rows={items}
            rowKey={(item) => String(item.seq)}
            empty={<p className="admin-muted admin-pad">{t.auditEmpty}</p>}
            columns={[
              {
                key: "when",
                header: t.auditWhen,
                render: (item) => (
                  <time dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString()}</time>
                ),
              },
              {
                key: "action",
                header: t.auditActionColumn,
                primary: true,
                render: (item) => <code>{item.action}</code>,
              },
              { key: "actor", header: t.auditActor, render: (item) => item.actor_kind },
              {
                key: "decision",
                header: t.auditDecision,
                render: (item) => (
                  <StatusBadge
                    tone={item.decision === "deny" ? "bad" : item.result === "success" ? "ok" : "warn"}
                  >
                    {item.decision}/{item.result}
                  </StatusBadge>
                ),
              },
              {
                key: "details",
                header: t.auditDetails,
                render: (item) => (
                  <span className="admin-mono">
                    {item.resource_type ? `${item.resource_type} — ` : ""}
                    {contextText(item.context)}
                  </span>
                ),
              },
            ]}
          />
        ) : null}
        {query.hasNextPage ? (
          <div className="admin-pad">
            <Button
              variant="secondary"
              onClick={() => void query.fetchNextPage()}
              disabled={query.isFetchingNextPage}
            >
              {t.auditMore}
            </Button>
          </div>
        ) : null}
      </AdminSection>
    </AdminPage>
  );
}
