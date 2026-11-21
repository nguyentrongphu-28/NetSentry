import React, { useState, useEffect } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { UserRecord, UserRole } from "../../types/api";
import { apiFetch, ApiClientError } from "../../services/apiClient";
import { STRINGS } from "../../i18n/strings";

export interface EditUserDialogProps {
  user: UserRecord | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function EditUserDialog({
  user,
  isOpen,
  onClose,
  onSuccess,
}: EditUserDialogProps): React.JSX.Element {
  const [role, setRole] = useState<UserRole>("operator");
  const [isActive, setIsActive] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRole(user.role);
      setIsActive(user.is_active);
      setError(null);
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!user) return;
    setError(null);

    setIsSubmitting(true);
    try {
      await apiFetch(`/api/v1/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          role,
          is_active: isActive,
        }),
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.code === "LAST_ADMIN" || err.status === 409) {
          setError(STRINGS.users.errorLastAdmin);
        } else {
          setError(err.message || "Không thể cập nhật người dùng.");
        }
      } else {
        setError("Lỗi kết nối máy chủ.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen && Boolean(user)}
      onClose={onClose}
      title={`Cập nhật tài khoản: ${user?.username}`}
      description="Chỉnh sửa vai trò phân quyền và trạng thái hoạt động của tài khoản."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} type="button">
            Hủy
          </Button>
          <Button
            variant="primary"
            isLoading={isSubmitting}
            disabled={isSubmitting}
            onClick={handleSubmit}
            type="submit"
            form="edit-user-form"
          >
            {isSubmitting ? "Đang lưu..." : "Lưu thay đổi"}
          </Button>
        </>
      }
    >
      <form id="edit-user-form" onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="edit-role-select" className="block text-xs font-semibold text-gray-700">
            Vai trò
          </label>
          <select
            id="edit-role-select"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            disabled={isSubmitting}
            className="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="admin">Quản trị viên (admin)</option>
            <option value="operator">Vận hành (operator)</option>
            <option value="viewer">Chỉ xem (viewer)</option>
          </select>
        </div>

        <div className="flex items-center space-x-3 pt-2">
          <input
            id="edit-active-toggle"
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            disabled={isSubmitting}
            className="h-4 w-4 rounded text-indigo-600 focus:ring-indigo-500 border-gray-300"
          />
          <label htmlFor="edit-active-toggle" className="text-sm font-medium text-gray-700 cursor-pointer">
            Cho phép tài khoản hoạt động
          </label>
        </div>
        {!isActive && (
          <p className="text-xs text-amber-600">
            Khi vô hiệu hóa, mọi phiên đăng nhập của người dùng này sẽ bị thu hồi ngay lập tức.
          </p>
        )}
      </form>
    </Modal>
  );
}
