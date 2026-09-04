import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  Expense,
  ExpenseCreateInput,
  ExpenseFilters,
  ExpensePage,
  ExpenseUpdateInput,
  Uuid,
} from "@/types/api";

/**
 * Everything an expense touches: the list, the group header, balances, the
 * activity feed and every dashboard aggregate. Invalidating them together keeps
 * the UI honest — a stale balance after adding an expense is the one bug users
 * would actually notice.
 */
function invalidateExpenseWorld(
  queryClient: ReturnType<typeof useQueryClient>,
  groupId: Uuid | undefined,
) {
  void queryClient.invalidateQueries({ queryKey: ["expenses", groupId] });
  void queryClient.invalidateQueries({ queryKey: ["balances", groupId] });
  void queryClient.invalidateQueries({ queryKey: ["group", groupId] });
  void queryClient.invalidateQueries({ queryKey: ["groups"] });
  void queryClient.invalidateQueries({ queryKey: ["activity"] });
  void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
}

export function useExpenses(groupId: Uuid | undefined, filters: ExpenseFilters = {}) {
  return useQuery({
    queryKey: ["expenses", groupId, filters],
    queryFn: () =>
      api.get<ExpensePage>(`/groups/${groupId}/expenses`, {
        category_id: filters.category_id,
        paid_by: filters.paid_by,
        date_from: filters.date_from,
        date_to: filters.date_to,
        q: filters.q,
        limit: filters.limit ?? 50,
        offset: filters.offset ?? 0,
      }),
    enabled: Boolean(groupId),
  });
}

export function useExpense(expenseId: Uuid | undefined) {
  return useQuery({
    queryKey: ["expense", expenseId],
    queryFn: () => api.get<Expense>(`/expenses/${expenseId}`),
    enabled: Boolean(expenseId),
  });
}

export function useCreateExpense(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ExpenseCreateInput) =>
      api.post<Expense>(`/groups/${groupId}/expenses`, input),
    onSuccess: () => invalidateExpenseWorld(queryClient, groupId),
  });
}

export function useUpdateExpense(expenseId: Uuid, groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ExpenseUpdateInput) =>
      api.patch<Expense>(`/expenses/${expenseId}`, input),
    onSuccess: (expense) => {
      queryClient.setQueryData(["expense", expenseId], expense);
      invalidateExpenseWorld(queryClient, groupId);
    },
  });
}

export function useDeleteExpense(groupId: Uuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (expenseId: Uuid) => api.del<void>(`/expenses/${expenseId}`),
    onSuccess: (_data, expenseId) => {
      queryClient.removeQueries({ queryKey: ["expense", expenseId] });
      invalidateExpenseWorld(queryClient, groupId);
    },
  });
}
