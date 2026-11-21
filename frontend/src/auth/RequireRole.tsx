import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { UserRole } from "../types/api";

export interface RequireRoleProps {
  roles: UserRole[];
  children: React.ReactNode;
}

export function RequireRole({ roles, children }: RequireRoleProps): React.JSX.Element {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-gray-500 font-medium text-sm">Đang tải...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
