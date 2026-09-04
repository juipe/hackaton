import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Payment, PaymentCreateInput, Uuid } from "@/types/api";

export function usePayments(groupId: Uuid | undefined) {
  return useQuery({
    queryKey: ["payments", groupId],
    queryFn: () => api.get<Payment[]>(`/groups/${groupId}/payments`),
    enabled: Boolean(groupId),
  });
}

export function useCreatePayment(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PaymentCreateInput) =>
      api.post<Payment>(`/groups/${groupId}/payments`, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payments", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["balances", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
