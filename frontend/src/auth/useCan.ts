import { useAuth } from "./AuthProvider";
import { UserRole } from "../types/api";

export type AppAction =
  | "device:create"
  | "device:delete"
  | "audit:run"
  | "user:manage"
  | "events:read";

const ROLE_PERMISSIONS: Record<UserRole, AppAction[]> = {
  admin: ["device:create", "device:delete", "audit:run", "user:manage", "events:read"],
  operator: ["device:create", "audit:run"],
  viewer: [],
};

export function useCan(action: AppAction): boolean {
  const { user } = useAuth();
  if (!user) return false;
  const permissions = ROLE_PERMISSIONS[user.role] || [];
  return permissions.includes(action);
}
