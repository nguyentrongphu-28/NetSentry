import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Shield, KeyRound, ArrowRight, Loader2, Server, CheckCircle2, AlertCircle } from "lucide-react";
import { useApiKey } from "../hooks/useApiKey";
import { getHealth, listDevices } from "../services/devicesApi";
import { HealthResponse } from "../types/api";
import { ApiClientError, API_KEY_STORAGE_KEY } from "../services/apiClient";

export function ConnectPage(): React.JSX.Element {
  const { setApiKey, isAuthenticated } = useApiKey();
  const navigate = useNavigate();
  const location = useLocation();

  const [inputKey, setInputKey] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(() => {
    const state = location.state as { message?: string } | null;
    return state?.message || null;
  });
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [serverStatus, setServerStatus] = useState<"checking" | "online" | "offline">("checking");

  // If already authenticated, redirect to /
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Check health
  useEffect(() => {
    let active = true;
    getHealth()
      .then((data) => {
        if (active) {
          setHealth(data);
          setServerStatus("online");
        }
      })
      .catch(() => {
        if (active) {
          setServerStatus("offline");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    const trimmed = inputKey.trim();
    if (!trimmed) {
      setErrorMsg("Vui lòng nhập khóa API.");
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    // Save temporary key to test endpoint
    try {
      sessionStorage.setItem(API_KEY_STORAGE_KEY, trimmed);
      await listDevices();
      // Valid! Persist to auth context
      setApiKey(trimmed);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      sessionStorage.removeItem(API_KEY_STORAGE_KEY);
      if (err instanceof ApiClientError) {
        if (err.status === 401) {
          setErrorMsg("Khóa API không đúng.");
        } else if (err.code === "NETWORK_ERROR") {
          setErrorMsg("Không kết nối được tới máy chủ API.");
        } else {
          setErrorMsg(err.message || "Xác thực thất bại.");
        }
      } else {
        setErrorMsg("Không kết nối được tới máy chủ API.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center text-indigo-600">
          <Shield className="w-12 h-12" />
        </div>
        <h2 className="mt-4 text-center text-3xl font-extrabold text-gray-900 tracking-tight">
          NetSentry Dashboard
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          Kết nối tới máy chủ quản lý và kiểm toán thiết bị mạng
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-sm border border-gray-200 sm:rounded-xl sm:px-10">
          {/* Server Health Status Banner */}
          <div className="mb-6 p-3 bg-gray-50 rounded-lg border border-gray-200 flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2">
              <Server className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">Trạng thái máy chủ:</span>
            </div>
            <div>
              {serverStatus === "online" && (
                <span className="inline-flex items-center text-emerald-700 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-500" />
                  Đang hoạt động (v{health?.version})
                </span>
              )}
              {serverStatus === "offline" && (
                <span className="inline-flex items-center text-rose-700 font-medium">
                  <AlertCircle className="w-3.5 h-3.5 mr-1 text-rose-500" />
                  Không thể kết nối
                </span>
              )}
              {serverStatus === "checking" && (
                <span className="text-gray-400">Đang kiểm tra...</span>
              )}
            </div>
          </div>

          {errorMsg && (
            <div
              role="alert"
              className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700 flex items-start space-x-2"
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-500 mt-0.5" />
              <div>{errorMsg}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-x-0 space-y-5">
            <div>
              <label htmlFor="api-key-input" className="block text-sm font-medium text-gray-700">
                Khóa API (X-API-Key)
              </label>
              <div className="mt-1 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <KeyRound className="h-5 w-5 text-gray-400" aria-hidden="true" />
                </div>
                <input
                  id="api-key-input"
                  name="apiKey"
                  type="password"
                  autoComplete="off"
                  value={inputKey}
                  onChange={(e) => setInputKey(e.target.value)}
                  placeholder="Nhập API key của máy chủ NetSentry"
                  disabled={isLoading}
                  className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                />
              </div>
              <p className="mt-1.5 text-xs text-gray-500">
                Khóa chỉ được lưu trong phiên duyệt web (sessionStorage) và tự xóa khi đóng tab.
              </p>
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex justify-center items-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Đang kết nối...
                  </>
                ) : (
                  <>
                    <span>Kết nối</span>
                    <ArrowRight className="w-4 h-4 ml-1.5" />
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
