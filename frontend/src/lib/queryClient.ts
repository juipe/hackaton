import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // A 401 means "sign in", and a 4xx means the request was wrong; neither
      // gets better by trying again. Only transient failures are worth a retry.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          return false;
        }
        return failureCount < 2;
      },
    },
    mutations: { retry: false },
  },
});
