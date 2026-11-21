import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { UserRecord } from "../../types/api";
import { apiFetch, ApiClientError } from "../../services/apiClient";

export interface ResetPasswordDialogProps {
  user: UserRecord | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ResetPasswordDialog({
  user,
  isOpen,
  onClose,
  onSuccess,
}: ResetPasswordDialogProps): React.JSX.Element {
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const resetForm = (): void => {
    setNewPassword("");
    setError(null);
  };

  const handleClose = (): void => {
    resetForm();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!user) return;
    setError(null);

    if (newPassword.length < 12) {
      setError("Mật khẩu mới phải có ít nhất 12 ký tự.");
      return;
    }

    setIsSubmitting(true);
    try {
      await apiFetch(`/api/v1/users/${user.id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({
          new_password: newPassword,
        }),
      });
      resetForm();
      onSuccess();
      onClose();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.code === "WEAK_PASSWORD" || err.status === 422) {
          setError(err.message || "Mật khẩu không đạt yêu cầu độ mạnh.");
        } else {
          setError(err.message || "Không thể đặt lại mật khẩu.");
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
      onClose={handleClose}
      title={`Đặt lại mật khẩu: ${user?.username}`}
      description="Đặt mật khẩu tạm thời cho người dùng. Mọi phiên hoạt động hiện tại sẽ bị thu hồi và người dùng phải đổi mật khẩu khi đăng nhập."
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
            form="reset-password-form"
          >
            {isSubmitting ? "Đang đặt lại..." : "Đặt lại mật khẩu"}
          </Button>
        </>
      }
    >
      <form id="reset-password-form" onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="reset-new-password" className="block text-xs font-semibold text-gray-700">
            Mật khẩu tạm mới *
          </label>
          <input
            id="reset-new-password"
            type="password"
            required
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={isSubmitting}
            placeholder="Tối thiểu 12 ký tự"
            className="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <p className="mt-1 text-xs text-gray-500">
            Mật khẩu tạm thời không được hiển thị lại sau khi lưu. Hãy gửi mật khẩu này cho người dùng qua kênh an toàn.
          </p>
        </div>
      </form>
    </Modal>
  );
}
