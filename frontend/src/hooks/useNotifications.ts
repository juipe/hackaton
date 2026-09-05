import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Notification } from "@/types/api";

export const NOTIFICATIONS_QUERY_KEY = ["notifications"] as const;

/**
 * Debt reminders for the signed-in user — at most 10, newest first, already
 * filtered server-side to what's past its 10-second delay. Polled, not
 * pushed: there is no websocket in this app, and a bell that is a few tens of
 * seconds behind is an acceptable trade for not adding one.
 *
 * The global `queryClient` default (`staleTime: 30_000`, `refetchOnWindowFocus:
 * false`) is meant for data that doesn't change from other tabs/actions on its
 * own — notifications don't fit that: a budget threshold or debt reminder can
 * appear at any time from an action the bell itself has no way to know about.
 * Overridden here, per-query, so it doesn't affect any other screen: always
 * stale (so remounting/refocusing refetches instead of serving a cached
 * "nothing yet"), and refetch on window focus too, on top of the interval.
 */
export function useNotifications() {
  return useQuery({
    queryKey: NOTIFICATIONS_QUERY_KEY,
    queryFn: () => api.get<Notification[]>("/notifications"),
    refetchInterval: 30_000,
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}

/** Marks every currently-visible reminder read — called when the panel opens. */
export function useMarkNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/notifications/read"),
    onSuccess: () => {
      queryClient.setQueryData<Notification[]>(NOTIFICATIONS_QUERY_KEY, (current) =>
        current?.map((notification) => ({ ...notification, is_read: true })),
      );
    },
  });
}
