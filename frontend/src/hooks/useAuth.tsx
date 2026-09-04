/**
 * Auth state.
 *
 * There is no token in JavaScript to hold — the session lives in an HttpOnly
 * cookie — so "am I signed in?" is answered by asking the server once and caching
 * the result under `["auth","me"]`. A 401 is a normal answer here, not an error.
 */

import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import type { LoginInput, RegisterInput, UserPublic } from "@/types/api";

interface AuthContextValue {
  user: UserPublic | null;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<UserPublic>;
  register: (input: RegisterInput) => Promise<UserPublic>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AUTH_QUERY_KEY = ["auth", "me"] as const;

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const { data, isPending } = useQuery({
    queryKey: AUTH_QUERY_KEY,
    queryFn: async () => {
      try {
        return await api.get<UserPublic>("/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.isUnauthorized) return null;
        throw error;
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });

  const loginMutation = useMutation({
    mutationFn: (input: LoginInput) => api.post<UserPublic>("/auth/login", input),
  });

  const registerMutation = useMutation({
    mutationFn: (input: RegisterInput) => api.post<UserPublic>("/auth/register", input),
  });

  const login = useCallback(
    async (input: LoginInput) => {
      const user = await loginMutation.mutateAsync(input);
      queryClient.setQueryData(AUTH_QUERY_KEY, user);
      return user;
    },
    [loginMutation, queryClient],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const user = await registerMutation.mutateAsync(input);
      queryClient.setQueryData(AUTH_QUERY_KEY, user);
      return user;
    },
    [registerMutation, queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await api.post<void>("/auth/logout");
    } finally {
      // Whatever the server said, this browser is done with the session: drop
      // every cached query so no group data survives into the next account.
      queryClient.setQueryData(AUTH_QUERY_KEY, null);
      queryClient.clear();
    }
  }, [queryClient]);

  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: data ?? null,
      isLoading: isPending,
      login,
      register,
      logout,
      refresh,
    }),
    [data, isPending, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

/** The signed-in user, for screens already behind `RequireAuth`. */
export function useCurrentUser(): UserPublic {
  const { user } = useAuth();
  if (!user) throw new Error("useCurrentUser used outside an authenticated route");
  return user;
}
