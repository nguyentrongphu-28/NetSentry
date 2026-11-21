import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogOut, Shield, Activity, Users, ShieldAlert } from "lucide-react";
import { useAuth } from "../../auth/AuthProvider";
import { useCan } from "../../auth/useCan";
import { getHealth } from "../../services/devicesApi";
import { HealthResponse } from "../../types/api";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps): React.JSX.Element {
  const { user, logout } = useAuth();
  const canManageUsers = useCan("user:manage");
  const canReadEvents = useCan("events:read");
  const navigate = useNavigate();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isOnline, setIsOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    getHealth()
      .then((data) => {
        if (mounted) {
          setHealth(data);
          setIsOnline(data.status === "ok");
        }
      })
      .catch(() => {
        if (mounted) {
          setIsOnline(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleLogout = async (): Promise<void> => {
    await logout();
    navigate("/login");
  };

  const roleBadgeColors: Record<string, string> = {
    admin: "bg-purple-100 text-purple-700 border-purple-200",
    operator: "bg-blue-100 text-blue-700 border-blue-200",
    viewer: "bg-gray-100 text-gray-700 border-gray-200",
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col text-gray-900">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <Link to="/" className="flex items-center space-x-2 text-indigo-600 hover:text-indigo-700">
              <Shield className="w-7 h-7" />
              <span className="font-bold text-xl tracking-tight text-gray-900">NetSentry</span>
            </Link>

            <nav className="hidden md:flex items-center space-x-1">
              <Link
                to="/"
                className="px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-indigo-600 hover:bg-gray-50 rounded-md transition-colors"
              >
                Thiết bị
              </Link>
              {canManageUsers && (
                <Link
                  to="/users"
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-indigo-600 hover:bg-gray-50 rounded-md transition-colors"
                >
                  <Users className="w-4 h-4 text-gray-500" />
                  <span>Người dùng</span>
                </Link>
              )}
              {canReadEvents && (
                <Link
                  to="/security-events"
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-indigo-600 hover:bg-gray-50 rounded-md transition-colors"
                >
                  <ShieldAlert className="w-4 h-4 text-gray-500" />
                  <span>Nhật ký bảo mật</span>
                </Link>
              )}
            </nav>
          </div>

          <div className="flex items-center space-x-4">
            {/* Server status pill */}
            <div className="hidden sm:flex items-center space-x-1.5 text-xs bg-gray-50 border border-gray-200 px-2.5 py-1 rounded-full">
              <Activity className="w-3.5 h-3.5 text-gray-400" />
              {isOnline === true ? (
                <>
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-gray-700 font-medium">
                    Máy chủ v{health?.version || "0.1.0"}
                  </span>
                </>
              ) : isOnline === false ? (
                <>
                  <span className="inline-block w-2 h-2 rounded-full bg-rose-500" />
                  <span className="text-rose-600 font-medium">Mất kết nối máy chủ</span>
                </>
              ) : (
                <span className="text-gray-400">Đang kiểm tra...</span>
              )}
            </div>

            {/* User Profile & Role */}
            {user && (
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-700">{user.username}</span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium border ${
                    roleBadgeColors[user.role] || roleBadgeColors.viewer
                  }`}
                >
                  {user.role}
                </span>
              </div>
            )}

            {/* Logout button */}
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center space-x-1.5 text-sm text-gray-600 hover:text-rose-600 px-3 py-1.5 rounded-md hover:bg-rose-50 transition-colors focus:outline-none focus:ring-2 focus:ring-rose-500"
            >
              <LogOut className="w-4 h-4" />
              <span>Đăng xuất</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white py-4 text-center text-xs text-gray-500">
        NetSentry &copy; {new Date().getFullYear()} – Nền tảng kiểm toán cấu hình thiết bị mạng
      </footer>
    </div>
  );
}
