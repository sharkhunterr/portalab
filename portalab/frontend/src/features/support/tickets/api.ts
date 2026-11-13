import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/** Support tickets, feedback and definitions API hooks (spec 016 Slice B). */
export type TicketCard = components["schemas"]["TicketCard"];
export type TicketDetail = components["schemas"]["TicketDetail"];
export type TicketCreate = components["schemas"]["TicketCreateIn"];
export type FeedbackDetail = components["schemas"]["FeedbackDetail"];
export interface FieldDef {
  key: string;
  label: string;
  type: "text" | "long_text" | "select" | "multi_select" | "number" | "boolean" | "date" | "user" | "rating";
  required?: boolean;
  options?: string[];
  visibility?: string;
}
export interface PrecheckResult {
  incidents: {
    state: string;
    items: Array<{ id: string; reference: string; title: string; severity: string; url: string }>;
  };
  knowledge: { state: string; items: Array<{ title: string; excerpt: string; url: string }> };
}

const KEY = ["support"] as const;

export function useTicketTypes() {
  return useQuery({
    queryKey: [...KEY, "types"],
    queryFn: async () => (await api.GET("/api/v1/tickets/types")).data ?? [],
  });
}

export async function precheck(serviceId: string | undefined, text: string): Promise<PrecheckResult> {
  const { data } = await api.POST("/api/v1/tickets/precheck", {
    body: { text, ...(serviceId ? { service_id: serviceId } : {}) },
  });
  return data as unknown as PrecheckResult;
}

export function useMyTickets() {
  return useQuery({
    queryKey: [...KEY, "mine"],
    queryFn: async () => (await api.GET("/api/v1/me/tickets")).data ?? [],
  });
}

export function useTicket(id: string) {
  return useQuery({
    queryKey: [...KEY, "ticket", id],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/tickets/{ticket_id}", { params: { path: { ticket_id: id } } }))
        .data as TicketDetail,
  });
}

export function useQueue(filters: { state?: string; unassigned?: boolean; q?: string; requester?: string }) {
  return useQuery({
    queryKey: [...KEY, "queue", filters],
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/support/tickets", {
          params: {
            query: {
              ...(filters.state ? { state: filters.state } : {}),
              ...(filters.unassigned ? { unassigned: true } : {}),
              ...(filters.q ? { q: filters.q } : {}),
              ...(filters.requester ? { requester: filters.requester } : {}),
            },
          },
        })
      ).data ?? { items: [], next_cursor: null },
  });
}

export function useTicketActions(id: string) {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const path = { params: { path: { ticket_id: id } } };
  return {
    create: useMutation({
      mutationFn: async (body: TicketCreate) =>
        (await api.POST("/api/v1/tickets", { body })).data as TicketDetail,
      onSettled: settle,
    }),
    comment: useMutation({
      mutationFn: async (body: string) =>
        (await api.POST("/api/v1/tickets/{ticket_id}/comments", { ...path, body: { body } })).data,
      onSettled: settle,
    }),
    note: useMutation({
      mutationFn: async (body: string) =>
        (await api.POST("/api/v1/tickets/{ticket_id}/internal-notes", { ...path, body: { body } })).data,
      onSettled: settle,
    }),
    transition: useMutation({
      mutationFn: async ({
        transition,
        comment,
        version,
      }: {
        transition: string;
        comment?: string;
        version: number;
      }) =>
        (
          await api.POST("/api/v1/tickets/{ticket_id}/transition", {
            ...path,
            body: { transition, ...(comment ? { comment } : {}) },
            headers: { "If-Match": String(version) },
          })
        ).data,
      onSettled: settle,
    }),
    assign: useMutation({
      mutationFn: async (assignee: string | null) =>
        (await api.POST("/api/v1/tickets/{ticket_id}/assign", { ...path, body: { assignee_id: assignee } }))
          .data,
      onSettled: settle,
    }),
    upload: useMutation({
      mutationFn: async (file: File) =>
        (
          await api.POST("/api/v1/tickets/{ticket_id}/attachments", {
            ...path,
            params: { path: { ticket_id: id }, query: { filename: file.name } },
            body: file as unknown as string,
            bodySerializer: (body: unknown) => body as BodyInit,
            headers: { "Content-Type": "application/octet-stream" },
          })
        ).data,
      onSettled: settle,
    }),
  };
}

export function useFeedbackDetail(id: string) {
  return useQuery({
    queryKey: [...KEY, "feedback", id],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/support/feedback/{feedback_id}", { params: { path: { feedback_id: id } } }))
        .data as FeedbackDetail,
  });
}

export function useFeedbackActions(id: string) {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: [...KEY, "feedback"] });
  return {
    convert: useMutation({
      mutationFn: async ({ target, confirmation }: { target: string; confirmation?: string }) =>
        (
          await api.POST("/api/v1/support/feedback/{feedback_id}/convert", {
            params: { path: { feedback_id: id } },
            body: {
              target_kind: target as components["schemas"]["FeedbackConvertIn"]["target_kind"],
              ...(confirmation ? { confirmation } : {}),
            },
          })
        ).data,
      onSettled: settle,
    }),
    review: useMutation({
      mutationFn: async (action: "review" | "dismiss") =>
        (
          await api.POST("/api/v1/support/feedback/{feedback_id}/{action}", {
            params: { path: { feedback_id: id, action } },
          })
        ).data,
      onSettled: settle,
    }),
  };
}
