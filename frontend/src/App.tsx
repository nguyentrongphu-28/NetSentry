import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiKeyProvider, useApiKey } from "./hooks/useApiKey";
import { AppShell } from "./components/layout/AppShell";
import { ConnectPage } from "./pages/ConnectPage";
import { DevicesPage } from "./pages/DevicesPage";
import { DeviceDetailPage } from "./pages/DeviceDetailPage";
import { AuditRunPage } from "./pages/AuditRunPage";
import { NotFoundPage } from "./pages/NotFoundPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
      staleTime: 10000,
    },
  },
});

function ProtectedLayout(): React.JSX.Element {
  const { isAuthenticated } = useApiKey();

  if (!isAuthenticated) {
    return <Navigate to="/connect" replace />;
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export function AppRoutes(): React.JSX.Element {
  return (
    <Routes>
      <Route path="/connect" element={<ConnectPage />} />

      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<DevicesPage />} />
        <Route path="/devices/:deviceId" element={<DeviceDetailPage />} />
        <Route path="/audits/:runId" element={<AuditRunPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export function App(): React.JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <ApiKeyProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ApiKeyProvider>
    </QueryClientProvider>
  );
}

export default App;
