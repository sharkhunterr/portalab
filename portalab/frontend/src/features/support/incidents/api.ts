import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/** Incidents API hooks (spec 016 Slice A). */
export type Incident = components["schemas"]["IncidentOut"];
export type Severity = Incident["severity"];

export function useIncidents(state?: "open" | "resolved") {
  return useQuery({
    queryKey: ["incidents", state ?? "all"],
    queryFn: async () =>
      ((await api.GET("/api/v1/incidents", { params: { query: state ? { state } : {} } })).data ??
        []) as Incident[],
    retry: false,
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ["incidents", "one", id],
    queryFn: async () =>
      (await api.GET("/api/v1/incidents/{incident_id}", { params: { path: { incident_id: id } } }))
        .data as Incident,
    retry: false,
  });
}

export type StaffAction =
  | {
      kind: "create";
      title: string;
      severity: Severity;
      summary: string;
      service_ids: string[];
      banner: boolean;
    }
  | {
      kind: "update";
      id: string;
      version: number;
      message: string;
      state?: "investigating" | "identified" | "monitoring";
    }
  | {
      kind: "patch";
      id: string;
      version: number;
      severity?: Severity;
      service_ids?: string[];
      banner?: boolean;
    }
  | { kind: "resolve"; id: string; version: number; message: string };

export function useIncidentStaff() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (action: StaffAction) => {
      switch (action.kind) {
        case "create":
          return (
            await api.POST("/api/v1/admin/incidents", {
              body: {
                title: action.title,
                severity: action.severity,
                summary: action.summary,
                service_ids: action.service_ids,
                banner: action.banner,
              },
            })
          ).data as Incident;
        case "update":
          return (
            await api.POST("/api/v1/admin/incidents/{incident_id}/updates", {
              params: { path: { incident_id: action.id } },
              headers: { "If-Match": String(action.version) },
              body: { message: action.message, state: action.state ?? null },
            })
          ).data as Incident;
        case "patch":
          return (
            await api.PATCH("/api/v1/admin/incidents/{incident_id}", {
              params: { path: { incident_id: action.id } },
              headers: { "If-Match": String(action.version) },
              body: {
                severity: action.severity ?? null,
                service_ids: action.service_ids ?? null,
                banner: action.banner ?? null,
              },
            })
          ).data as Incident;
        case "resolve":
          return (
            await api.POST("/api/v1/admin/incidents/{incident_id}/resolve", {
              params: { path: { incident_id: action.id } },
              headers: { "If-Match": String(action.version) },
              body: { message: action.message },
            })
          ).data as Incident;
      }
    },
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: ["incidents"] });
    },
  });
}
