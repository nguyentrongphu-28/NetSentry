import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  API_KEY_STORAGE_KEY,
  getStoredApiKey,
  setUnauthorizedHandler,
} from "../services/apiClient";

interface ApiKeyContextValue {
  apiKey: string | null;
  setApiKey: (key: string) => void;
  clearApiKey: () => void;
  isAuthenticated: boolean;
}

const ApiKeyContext = createContext<ApiKeyContextValue | undefined>(undefined);

export function ApiKeyProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const [apiKey, setApiKeyState] = useState<string | null>(() => getStoredApiKey());
  const queryClient = useQueryClient();

  const clearApiKey = useCallback(() => {
    try {
      sessionStorage.removeItem(API_KEY_STORAGE_KEY);
    } catch {
      // Ignored
    }
    setApiKeyState(null);
    queryClient.clear();
  }, [queryClient]);

  const setApiKey = useCallback((key: string) => {
    try {
      sessionStorage.setItem(API_KEY_STORAGE_KEY, key);
    } catch {
      // Ignored
    }
    setApiKeyState(key);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(clearApiKey);
    return () => {
      setUnauthorizedHandler(null);
    };
  }, [clearApiKey]);

  const value = useMemo<ApiKeyContextValue>(
    () => ({
      apiKey,
      setApiKey,
      clearApiKey,
      isAuthenticated: Boolean(apiKey),
    }),
    [apiKey, setApiKey, clearApiKey]
  );

  return <ApiKeyContext.Provider value={value}>{children}</ApiKeyContext.Provider>;
}

export function useApiKey(): ApiKeyContextValue {
  const context = useContext(ApiKeyContext);
  if (!context) {
    throw new Error("useApiKey must be used within an ApiKeyProvider");
  }
  return context;
}
