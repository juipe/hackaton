import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  CategoryBreakdown,
  DashboardParams,
  DashboardSummary,
  SpendingOverTime,
} from "@/types/api";

function toQuery(params: DashboardParams) {
  return {
    period: params.period ?? "all",
    date_from: params.period === "custom" ? params.date_from : undefined,
    date_to: params.period === "custom" ? params.date_to : undefined,
    group_id: params.group_id,
  };
}

/** A custom range is only a valid request once both ends are chosen. */
function isReady(params: DashboardParams): boolean {
  if (params.period !== "custom") return true;
  return Boolean(params.date_from && params.date_to);
}

export function useDashboardSummary(params: DashboardParams = {}) {
  return useQuery({
    queryKey: ["dashboard", "summary", params],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary", toQuery(params)),
    enabled: isReady(params),
  });
}

export function useSpendingByCategory(params: DashboardParams = {}) {
  return useQuery({
    queryKey: ["dashboard", "by-category", params],
    queryFn: () =>
      api.get<CategoryBreakdown>("/dashboard/spending-by-category", toQuery(params)),
    enabled: isReady(params),
  });
}

export function useSpendingOverTime(params: DashboardParams = {}) {
  return useQuery({
    queryKey: ["dashboard", "over-time", params],
    queryFn: () =>
      api.get<SpendingOverTime>("/dashboard/spending-over-time", toQuery(params)),
    enabled: isReady(params),
  });
}
