import React from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Home } from "lucide-react";

export function NotFoundPage(): React.JSX.Element {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
      <div className="w-16 h-16 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mb-4">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-bold text-gray-900 tracking-tight">404 – Không tìm thấy trang</h1>
      <p className="mt-2 text-base text-gray-600 max-w-md">
        Trang bạn yêu cầu không tồn tại, địa chỉ ID không hợp lệ hoặc đã bị di chuyển.
      </p>
      <div className="mt-6">
        <Link
          to="/"
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <Home className="w-4 h-4 mr-2" />
          Về bảng điều khiển
        </Link>
      </div>
    </div>
  );
}
