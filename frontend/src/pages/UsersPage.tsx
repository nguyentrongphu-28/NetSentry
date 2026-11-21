import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { UserPlus, UserCog, KeyRound, Shield, AlertCircle } from "lucide-react";
import { UserRecord } from "../types/api";
import { apiFetch } from "../services/apiClient";
import { STRINGS } from "../i18n/strings";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { CreateUserDialog } from "../components/users/CreateUserDialog";
import { EditUserDialog } from "../components/users/EditUserDialog";
import { ResetPasswordDialog } from "../components/users/ResetPasswordDialog";
import { formatDateTime, formatRelativeTime } from "../utils/format";

export function UsersPage(): React.JSX.Element {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [userToEdit, setUserToEdit] = useState<UserRecord | null>(null);
  const [userToReset, setUserToReset] = useState<UserRecord | null>(null);

  const {
    data: users,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<UserRecord[]>({
    queryKey: ["users"],
    queryFn: () => apiFetch<UserRecord[]>("/api/v1/users"),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            {STRINGS.users.title}
          </h1>
          <p className="mt-1 text-sm text-gray-500">{STRINGS.users.subtitle}</p>
        </div>
        <div>
          <Button
            variant="primary"
            icon={<UserPlus className="w-4 h-4" />}
            onClick={() => setIsCreateOpen(true)}
          >
            {STRINGS.users.createUser}
          </Button>
        </div>
      </div>

      {isLoading && (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Spinner size="lg" className="text-indigo-600" />
          <p className="text-sm text-gray-500">{STRINGS.users.loading}</p>
        </div>
      )}

      {isError && (
        <div role="alert" className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error instanceof Error ? error.message : STRINGS.users.errorLoad}</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            Thử lại
          </Button>
        </div>
      )}

      {!isLoading && !isError && (
        <div className="overflow-x-auto border border-gray-200 rounded-xl shadow-xs bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
            <thead className="bg-gray-50 text-gray-500 font-medium">
              <tr>
                <th scope="col" className="px-6 py-3.5">
                  {STRINGS.users.colUsername}
                </th>
                <th scope="col" className="px-6 py-3.5">
                  {STRINGS.users.colRole}
                </th>
                <th scope="col" className="px-6 py-3.5">
                  {STRINGS.users.colStatus}
                </th>
                <th scope="col" className="px-6 py-3.5">
                  {STRINGS.users.colLastLogin}
                </th>
                <th scope="col" className="px-6 py-3.5">
                  {STRINGS.users.colCreatedAt}
                </th>
                <th scope="col" className="px-6 py-3.5 text-right">
                  {STRINGS.users.colActions}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {users?.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50/80 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900 flex items-center space-x-2">
                    <Shield className="w-4 h-4 text-gray-400" />
                    <span>{u.username}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${
                        u.role === "admin"
                          ? "bg-purple-50 text-purple-700 border border-purple-200"
                          : u.role === "operator"
                          ? "bg-blue-50 text-blue-700 border border-blue-200"
                          : "bg-gray-100 text-gray-600 border border-gray-200"
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap space-x-1.5">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        u.is_active
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}
                    >
                      {u.is_active ? STRINGS.users.active : STRINGS.users.disabled}
                    </span>
                    {u.must_change_password && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-amber-50 text-amber-700 border border-amber-200">
                        {STRINGS.users.mustChangePassword}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-600 text-xs">
                    {u.last_login_at ? (
                      <span title={formatDateTime(u.last_login_at)}>
                        {formatRelativeTime(u.last_login_at)}
                      </span>
                    ) : (
                      <span className="text-gray-400 italic">Chưa đăng nhập</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500 text-xs font-mono">
                    {formatDateTime(u.created_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right space-x-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<UserCog className="w-3.5 h-3.5" />}
                      onClick={() => setUserToEdit(u)}
                    >
                      {STRINGS.users.editUser}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<KeyRound className="w-3.5 h-3.5 text-gray-500 hover:text-amber-600" />}
                      onClick={() => setUserToReset(u)}
                      aria-label={`Đặt lại mật khẩu cho ${u.username}`}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Dialogs */}
      <CreateUserDialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={() => void refetch()}
      />

      <EditUserDialog
        user={userToEdit}
        isOpen={Boolean(userToEdit)}
        onClose={() => setUserToEdit(null)}
        onSuccess={() => void refetch()}
      />

      <ResetPasswordDialog
        user={userToReset}
        isOpen={Boolean(userToReset)}
        onClose={() => setUserToReset(null)}
        onSuccess={() => void refetch()}
      />
    </div>
  );
}
