import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/** Proposals, votes and participation (spec 012, slice D). */
export type Proposal = components["schemas"]["CommunityProposalOut"];
export type ProposalInput = components["schemas"]["CommunityProposalIn"];
export type ParticipationRow = components["schemas"]["CommunityParticipationOut"];

const KEY = ["community", "proposals"] as const;

export function useProposals(mine = false) {
  return useQuery({
    queryKey: [...KEY, mine ? "mine" : "open"],
    queryFn: async () =>
      ((await api.GET("/api/v1/community/proposals", { params: { query: { mine } } })).data ??
        []) as Proposal[],
  });
}

export function useProposal(id: string) {
  return useQuery({
    queryKey: [...KEY, id],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/community/proposals/{proposal_id}", { params: { path: { proposal_id: id } } }))
        .data as Proposal,
  });
}

export function useParticipations(id: string) {
  return useQuery({
    queryKey: [...KEY, id, "participations"],
    queryFn: async () =>
      ((
        await api.GET("/api/v1/community/proposals/{proposal_id}/participations", {
          params: { path: { proposal_id: id } },
        })
      ).data ?? []) as ParticipationRow[],
  });
}

export function useProposalActions(id: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: KEY });
  const path = { params: { path: { proposal_id: id } } };
  return {
    vote: useMutation({
      mutationFn: async (cast: boolean) =>
        cast
          ? (await api.POST("/api/v1/community/proposals/{proposal_id}/vote", path)).data
          : (await api.DELETE("/api/v1/community/proposals/{proposal_id}/vote", path)).data,
      onSuccess: refresh,
    }),
    participate: useMutation({
      mutationFn: async (role: "contributor" | "tester" | "helper") =>
        (
          await api.POST("/api/v1/community/proposals/{proposal_id}/participation", {
            ...path,
            body: { role },
          })
        ).data,
      onSuccess: refresh,
    }),
    leave: useMutation({
      mutationFn: async () => api.DELETE("/api/v1/community/proposals/{proposal_id}/participation", path),
      onSuccess: refresh,
    }),
    recognize: useMutation({
      mutationFn: async (participationId: string) =>
        (
          await api.POST(
            "/api/v1/community/proposals/{proposal_id}/participations/{participation_id}/recognize",
            {
              params: { path: { proposal_id: id, participation_id: participationId } },
            },
          )
        ).data,
      onSuccess: refresh,
    }),
    help: useMutation({
      mutationFn: async (body: { help_wanted: boolean; note?: string | null }) =>
        (await api.PUT("/api/v1/community/proposals/{proposal_id}/help", { ...path, body })).data,
      onSuccess: refresh,
    }),
    withdraw: useMutation({
      mutationFn: async () =>
        (await api.POST("/api/v1/community/proposals/{proposal_id}/withdraw", path)).data,
      onSuccess: refresh,
    }),
  };
}

export function useCreateProposal() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProposalInput) =>
      (await api.POST("/api/v1/community/proposals", { body })).data as Proposal,
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useModeration() {
  const client = useQueryClient();
  const queue = useQuery({
    queryKey: [...KEY, "moderation"],
    queryFn: async () => ((await api.GET("/api/v1/admin/community/moderation")).data ?? []) as Proposal[],
  });
  const decide = useMutation({
    mutationFn: async ({ id, approve, reason }: { id: string; approve: boolean; reason: string }) => {
      const params = { params: { path: { proposal_id: id } }, body: { reason } };
      return approve
        ? (await api.POST("/api/v1/admin/community/moderation/proposals/{proposal_id}/approve", params)).data
        : (await api.POST("/api/v1/admin/community/moderation/proposals/{proposal_id}/reject", params)).data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
  return { queue, decide };
}
