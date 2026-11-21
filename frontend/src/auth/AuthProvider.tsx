import React, { createContext, useCallback, useContext, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { UserSummary, Capabilities } from "../types/api";
import { apiFetch, setUnauthorizedHandler } from "../services/apiClient";

export interface AuthContextValue {
  user: UserSummary | null;
  capabilities: Capabilities | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

interface MeResponse {
  user: UserSummary;
  capabilities: Capabilities;
}

const AUTH_QUERY_KEY = ["auth", "me"] as const;
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const queryClient = useQueryClient();

  const meQuery = useQuery<MeResponse | null>({
    queryKey: AUTH_QUERY_KEY,
    queryFn: async () => {
      try {
        return await apiFetch<MeResponse>("/api/v1/auth/me");
      } catch {
        return null; // not logged in (401) or server unreachable
      }
    },
    retry: false,
    staleTime: 30_000,
  });

  // Drop everything cached for the previous user, then mark as logged out.
  const clearSession = useCallback(() => {
    queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
    queryClient.setQueryData(AUTH_QUERY_KEY, null);
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  const refreshAuth = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
  }, [queryClient]);

  const login = useCallback(
    async (username: string, password: string) => {
      await apiFetch<{ user: UserSummary }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      await refreshAuth();
    },
    [refreshAuth],
  );

  const logout = useCallback(async () => {
    try {
      await apiFetch<void>("/api/v1/auth/logout", { method: "POST" });
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: meQuery.data?.user ?? null,
      capabilities: meQuery.data?.capabilities ?? null,
      isLoading: meQuery.isPending,
      login,
      logout,
      refreshAuth,
    }),
    [meQuery.data, meQuery.isPending, login, logout, refreshAuth],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      {/* Hidden marker so tests can wait until the first /auth/me finished. */}
      {!meQuery.isPending && <div data-testid="auth-ready" hidden />}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
