import React from "react";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { RequireRole } from "./auth/RequireRole";
import { AppShell } from "./components/layout/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { DevicesPage } from "./pages/DevicesPage";
import { DeviceDetailPage } from "./pages/DeviceDetailPage";
import { AuditRunPage } from "./pages/AuditRunPage";
import { UsersPage } from "./pages/UsersPage";
import { SecurityEventsPage } from "./pages/SecurityEventsPage";
import { RemediationPlansPage } from "./pages/RemediationPlansPage";
import { RemediationPlanDetailPage } from "./pages/RemediationPlanDetailPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: true,
        staleTime: 10000,
      },
    },
  });
}

function ProtectedLayout(): React.JSX.Element {
  return (
    <RequireAuth>
      <AppShell>
        <Outlet />
      </AppShell>
    </RequireAuth>
  );
}

export function AppRoutes(): React.JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />

      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<DevicesPage />} />
        <Route path="/devices/:deviceId" element={<DeviceDetailPage />} />
        <Route path="/audits/:runId" element={<AuditRunPage />} />
        <Route path="/remediation" element={<RemediationPlansPage />} />
        <Route path="/remediation/:planId" element={<RemediationPlanDetailPage />} />
        <Route
          path="/users"
          element={
            <RequireRole roles={["admin"]}>
              <UsersPage />
            </RequireRole>
          }
        />
        <Route
          path="/security-events"
          element={
            <RequireRole roles={["admin"]}>
              <SecurityEventsPage />
            </RequireRole>
          }
        />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export function App(): React.JSX.Element {
  const [client] = React.useState(() => createQueryClient());

  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
