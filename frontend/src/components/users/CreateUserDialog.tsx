import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { UserRole } from "../../types/api";
import { apiFetch, ApiClientError } from "../../services/apiClient";

export interface CreateUserDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function CreateUserDialog({
  isOpen,
  onClose,
  onSuccess,
}: CreateUserDialogProps): React.JSX.Element {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("operator");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const resetForm = (): void => {
    setUsername("");
    setPassword("");
    setRole("operator");
    setError(null);
  };

  const handleClose = (): void => {
    resetForm();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);

    const normUsername = username.trim();
    if (!normUsername || !password) {
      setError("Vui lòng điền đầy đủ thông tin.");
      return;
    }

    if (password.length < 12) {
      setError("Mật khẩu phải có độ dài tối thiểu 12 ký tự.");
      return;
    }

    setIsSubmitting(true);
    try {
      await apiFetch("/api/v1/users", {
        method: "POST",
        body: JSON.stringify({
          username: normUsername,
          password,
          role,
        }),
      });
      resetForm();
      onSuccess();
      onClose();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.code === "USER_EXISTS" || err.status === 409) {
          setError("Tên đăng nhập đã tồn tại trong hệ thống.");
        } else if (err.code === "WEAK_PASSWORD" || err.status === 422) {
          setError(err.message || "Mật khẩu không đạt yêu cầu độ mạnh.");
        } else {
          setError(err.message || "Không thể tạo người dùng.");
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
      isOpen={isOpen}
      onClose={handleClose}
      title="Tạo người dùng mới"
      description="Thêm tài khoản truy cập hệ thống NetSentry và phân quyền vai trò."
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} type="button">
            Hủy
          </Button>
          <Button
            variant="primary"
            isLoading={isSubmitting}
            disabled={isSubmitting}
            onClick={handleSubmit}
            type="submit"
            form="create-user-form"
          >
            {isSubmitting ? "Đang tạo..." : "Tạo người dùng"}
          </Button>
        </>
      }
    >
      <form id="create-user-form" onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="create-username-input" className="block text-xs font-semibold text-gray-700">
            Tên đăng nhập *
          </label>
          <input
            id="create-username-input"
            type="text"
            required
            autoComplete="off"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isSubmitting}
            placeholder="vd: bob"
            className="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label htmlFor="create-password-input" className="block text-xs font-semibold text-gray-700">
            Mật khẩu khởi tạo *
          </label>
          <input
            id="create-password-input"
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isSubmitting}
            placeholder="Tối thiểu 12 ký tự"
            className="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <p className="mt-1 text-xs text-gray-500">
            Tối thiểu 12 ký tự. Người dùng sẽ phải đổi mật khẩu ở lần đăng nhập đầu tiên.
          </p>
        </div>

        <div>
          <label htmlFor="create-role-select" className="block text-xs font-semibold text-gray-700">
            Vai trò *
          </label>
          <select
            id="create-role-select"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            disabled={isSubmitting}
            className="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="operator">Vận hành (operator)</option>
            <option value="admin">Quản trị viên (admin)</option>
            <option value="viewer">Chỉ xem (viewer)</option>
          </select>
        </div>
      </form>
    </Modal>
  );
}
