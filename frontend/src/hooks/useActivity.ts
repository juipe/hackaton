import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Activity, Uuid } from "@/types/api";

export function useGroupActivity(groupId: Uuid | undefined, limit = 20) {
  return useQuery({
    queryKey: ["activity", groupId, limit],
    queryFn: () => api.get<Activity[]>(`/groups/${groupId}/activity`, { limit }),
    enabled: Boolean(groupId),
  });
}

export function useRecentActivity(limit = 20) {
  return useQuery({
    queryKey: ["activity", "all", limit],
    queryFn: () => api.get<Activity[]>("/activity", { limit }),
  });
}
