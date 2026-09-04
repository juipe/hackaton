import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Category } from "@/types/api";

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    // The category set only changes with a deploy, so it never needs refetching.
    staleTime: Infinity,
    queryFn: () => api.get<Category[]>("/categories"),
  });
}
