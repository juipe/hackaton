import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Notification } from "@/types/api";

export const NOTIFICATIONS_QUERY_KEY = ["notifications"] as const;

/**
 * Debt reminders for the signed-in user — at most 10, newest first, already
 * filtered server-side to what's past its 10-second delay. Polled, not
 * pushed: there is no websocket in this app, and a bell that is a few tens of
 * seconds behind is an acceptable trade for not adding one.
 */
export function useNotifications() {
  return useQuery({
    queryKey: NOTIFICATIONS_QUERY_KEY,
    queryFn: () => api.get<Notification[]>("/notifications"),
    refetchInterval: 30_000,
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
