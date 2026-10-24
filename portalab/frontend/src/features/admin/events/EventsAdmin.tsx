import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../../api/client";
import {
  AdminPage,
  AdminSection,
  AdminTable,
  FormActions,
  FormGrid,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useStrings } from "../../../i18n/hooks/useStrings";
import { ApiError, DataRegion } from "../../../state/regions";

/** Event operations (spec 007 T031): deliveries and dead letters, quarantine, replay. Strings for i18n (026). */
export const eventsStrings = {
  title: "Events",
  description:
    "The event pipeline: deliveries that failed for good, payloads set aside, and projection rebuilds.",
  consumer: "Consumer",
  event: "Event",
  attempts: "Attempts",
  error: "Last error",
  type: "Type",
  reason: "Reason",
  deadLetters: "Dead letters",
  noDeadLetters: "No dead letter.",
  quarantine: "Quarantine",
  noQuarantine: "Nothing in quarantine.",
  release: "Release",
  discard: "Discard",
  replayTitle: "Rebuild a projection",
  projectionField: "Projection",
  replayStart: "Rebuild",
  replayConfirm: "Confirm the rebuild",
  replayDone: (count: number) => `Rebuilt from ${count} events.`,
  genericError: "The operation was refused.",
} as const;

/** Issue 201: the page's texts in the administrator's language (``admin:events.*``). */
export function useEventsStrings() {
  return useStrings(eventsStrings, "admin:events", { replayDone: ["count"] });
}

interface Delivery {
  consumer: string;
  event_id: string;
  status: string;
  attempts: number;
  last_error: string | null;
}

interface QuarantineItem {
  id: string;
  event_type: string;
  reason: string;
  detail: string;
}

function DeadLetters() {
  const s = useEventsStrings();
  return (
    <DataRegion<Delivery[]>
      label={s.deadLetters}
      queryKey={["admin", "events", "dead"]}
      queryFn={async () =>
        (
          (await api.GET("/api/v1/admin/events/deliveries", { params: { query: { status: "dead" } } }))
            .data as unknown as { items: Delivery[] }
        ).items
      }
    >
      {(items) => (
        <AdminTable<Delivery>
          label={s.deadLetters}
          rows={items}
          rowKey={(item) => `${item.consumer}-${item.event_id}`}
          empty={<p className="admin-muted admin-pad">{s.noDeadLetters}</p>}
          columns={[
            {
              key: "consumer",
              header: s.consumer,
              primary: true,
              render: (i) => <code>{i.consumer}</code>,
            },
            {
              key: "event",
              header: s.event,
              render: (i) => <span className="admin-mono">{i.event_id}</span>,
            },
            { key: "attempts", header: s.attempts, align: "end", render: (i) => i.attempts },
            {
              key: "error",
              header: s.error,
              render: (i) => <span className="admin-mono">{i.last_error ?? "—"}</span>,
            },
          ]}
        />
      )}
    </DataRegion>
  );
}

function QuarantineList() {
  const s = useEventsStrings();
  const queryClient = useQueryClient();
  const resolve = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: "release" | "discard" }) => {
      await api.POST("/api/v1/admin/events/quarantine/{item_id}/{action}", {
        params: { path: { item_id: id, action } },
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "events", "quarantine"] }),
  });
  return (
    <DataRegion<QuarantineItem[]>
      label={s.quarantine}
      queryKey={["admin", "events", "quarantine"]}
      queryFn={async () =>
        ((await api.GET("/api/v1/admin/events/quarantine")).data as unknown as { items: QuarantineItem[] })
          .items
      }
    >
      {(items) => (
        <AdminTable<QuarantineItem>
          label={s.quarantine}
          rows={items}
          rowKey={(item) => item.id}
          empty={<p className="admin-muted admin-pad">{s.noQuarantine}</p>}
          columns={[
            {
              key: "type",
              header: s.type,
              primary: true,
              render: (i) => <code>{i.event_type}</code>,
            },
            {
              key: "reason",
              header: s.reason,
              render: (i) => <StatusBadge tone="warn">{i.reason}</StatusBadge>,
            },
            {
              key: "detail",
              header: s.error,
              render: (i) => <span className="admin-mono">{i.detail}</span>,
            },
          ]}
          actions={(item) => (
            <>
              <Button variant="secondary" onClick={() => resolve.mutate({ id: item.id, action: "release" })}>
                {s.release}
              </Button>
              <Button variant="ghost" onClick={() => resolve.mutate({ id: item.id, action: "discard" })}>
                {s.discard}
              </Button>
            </>
          )}
        />
      )}
    </DataRegion>
  );
}

function Replay() {
  const s = useEventsStrings();
  const ids = { field: useId(), title: useId() };
  const [projection, setProjection] = useState("");
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: async () =>
      (await api.POST("/api/v1/admin/replay", { body: { projection, confirmation } })).data as unknown as {
        processed: number;
      },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "authz.confirmation_required") {
        setConfirmation(String(error.extensions.confirmation));
      }
    },
    onSuccess: () => setConfirmation(null),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  const awaitingConfirmation = confirmation !== null && !mutation.isSuccess;
  return (
    <form onSubmit={submit} className="admin-form">
      {mutation.isError && !awaitingConfirmation ? <p role="alert">{s.genericError}</p> : null}
      {mutation.isSuccess ? <p role="status">{s.replayDone(mutation.data.processed)}</p> : null}
      <FormGrid>
        <TextField
          id={ids.field}
          label={s.projectionField}
          required
          value={projection}
          onChange={(event) => setProjection(event.target.value)}
        />
      </FormGrid>
      <FormActions>
        <Button
          type="submit"
          variant={awaitingConfirmation ? "danger" : "primary"}
          disabled={mutation.isPending}
        >
          {awaitingConfirmation ? s.replayConfirm : s.replayStart}
        </Button>
      </FormActions>
    </form>
  );
}

export function EventsAdmin() {
  const s = useEventsStrings();
  return (
    <AdminPage icon="zap" title={s.title} description={s.description}>
      <AdminSection title={s.deadLetters} icon="alert" flush>
        <DeadLetters />
      </AdminSection>
      <AdminSection title={s.quarantine} icon="lock" flush>
        <QuarantineList />
      </AdminSection>
      <AdminSection title={s.replayTitle} icon="sync">
        <Replay />
      </AdminSection>
    </AdminPage>
  );
}
