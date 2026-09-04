import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { LoadingState } from "@/components/common/LoadingState";
import { Wordmark } from "@/components/layout/Wordmark";
import { useAuth } from "@/hooks/useAuth";

export interface RequireAuthProps {
  children: ReactNode;
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-app">
        <Wordmark />
        <LoadingState label="Проверяем вход…" className="py-0" />
      </div>
    );
  }

  if (!user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  return <>{children}</>;
}
