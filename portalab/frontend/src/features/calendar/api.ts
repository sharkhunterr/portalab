import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Calendar API hooks (spec 011). */
export type CalendarView = components["schemas"]["CalendarOut"];
export type CalendarItem = components["schemas"]["CalendarItemOut"];

export function useCalendar(from: Date, to: Date) {
  return useQuery({
    queryKey: ["calendar", from.toISOString(), to.toISOString()],
    queryFn: async () =>
      (
        await api.GET("/api/v1/calendar", {
          params: { query: { from: from.toISOString(), to: to.toISOString() } },
        })
      ).data as CalendarView,
  });
}

export function useReminders() {
  return useQuery({
    queryKey: ["calendar", "reminders"],
    queryFn: async () => (await api.GET("/api/v1/me/calendar/reminders")).data ?? [],
  });
}

export function useReminderActions() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: ["calendar", "reminders"] });
  const add = useMutation({
    mutationFn: async (body: components["schemas"]["CalendarReminderIn"]) =>
      (await api.POST("/api/v1/me/calendar/reminders", { body })).data,
    onSettled: settle,
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api.DELETE("/api/v1/me/calendar/reminders/{reminder_id}", { params: { path: { reminder_id: id } } }),
    onSettled: settle,
  });
  return { add, remove };
}
