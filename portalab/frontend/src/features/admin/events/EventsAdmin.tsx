import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../../api/client";
import { ApiError, DataRegion } from "../../../state/regions";

/** Event operations (spec 007 T031): deliveries and dead letters, quarantine, replay. Strings for i18n (026). */
export const eventsStrings = {
  title: "Events",
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
  return (
    <DataRegion<Delivery[]>
      label={eventsStrings.deadLetters}
      queryKey={["admin", "events", "dead"]}
      queryFn={async () =>
        (
          (await api.GET("/api/v1/admin/events/deliveries", { params: { query: { status: "dead" } } }))
            .data as unknown as { items: Delivery[] }
        ).items
      }
    >
      {(items) =>
        items.length === 0 ? (
          <p>{eventsStrings.noDeadLetters}</p>
        ) : (
          <ul>
            {items.map((item) => (
              <li key={`${item.consumer}-${item.event_id}`}>
                {item.consumer} · {item.event_id} · {item.attempts} — {item.last_error}
              </li>
            ))}
          </ul>
        )
      }
    </DataRegion>
  );
}

function QuarantineList() {
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
      label={eventsStrings.quarantine}
      queryKey={["admin", "events", "quarantine"]}
      queryFn={async () =>
        ((await api.GET("/api/v1/admin/events/quarantine")).data as unknown as { items: QuarantineItem[] })
          .items
      }
    >
      {(items) =>
        items.length === 0 ? (
          <p>{eventsStrings.noQuarantine}</p>
        ) : (
          <ul>
            {items.map((item) => (
              <li key={item.id}>
                {item.event_type} · {item.reason} — {item.detail}{" "}
                <button type="button" onClick={() => resolve.mutate({ id: item.id, action: "release" })}>
                  {eventsStrings.release}
                </button>{" "}
                <button type="button" onClick={() => resolve.mutate({ id: item.id, action: "discard" })}>
                  {eventsStrings.discard}
                </button>
              </li>
            ))}
          </ul>
        )
      }
    </DataRegion>
  );
}

function Replay() {
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
    <form onSubmit={submit} aria-labelledby={ids.title} className="auth-form">
      <h3 id={ids.title}>{eventsStrings.replayTitle}</h3>
      {mutation.isError && !awaitingConfirmation ? <p role="alert">{eventsStrings.genericError}</p> : null}
      {mutation.isSuccess ? <p role="status">{eventsStrings.replayDone(mutation.data.processed)}</p> : null}
      <label htmlFor={ids.field}>{eventsStrings.projectionField}</label>
      <input
        id={ids.field}
        required
        value={projection}
        onChange={(event) => setProjection(event.target.value)}
      />
      <button type="submit" disabled={mutation.isPending}>
        {awaitingConfirmation ? eventsStrings.replayConfirm : eventsStrings.replayStart}
      </button>
    </form>
  );
}

export function EventsAdmin() {
  return (
    <div className="account-page">
      <h2>{eventsStrings.title}</h2>
      <DeadLetters />
      <QuarantineList />
      <Replay />
    </div>
  );
}
