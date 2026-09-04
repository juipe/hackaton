import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { GroupBalances, SimplifyPreview, Uuid } from "@/types/api";

export function useBalances(groupId: Uuid | undefined) {
  return useQuery({
    queryKey: ["balances", groupId],
    queryFn: () => api.get<GroupBalances>(`/groups/${groupId}/balances`),
    enabled: Boolean(groupId),
  });
}

/**
 * Simplification is a recommendation, not a mutation: the server computes the
 * minimal set of transfers without touching anyone's balance. It is a POST only
 * because it can optionally record an activity entry.
 */
export function useSimplifyDebts(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    // Declared as a required boolean rather than a defaulted parameter: a default
    // would let TanStack infer the variables type as `void`, and every call site
    // passing true/false would then fail to type-check.
    mutationFn: (recordActivity: boolean) =>
      api.post<SimplifyPreview>(`/groups/${groupId}/simplify-debts`, {
        record_activity: recordActivity,
      }),
    onSuccess: (_data, recordActivity) => {
      if (recordActivity) {
        void queryClient.invalidateQueries({ queryKey: ["activity"] });
      }
    },
  });
}
