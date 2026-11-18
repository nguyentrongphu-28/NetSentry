import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "./Button";

export interface ErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorBanner({
  title = "Đã xảy ra lỗi",
  message,
  onRetry,
  className = "",
}: ErrorBannerProps): React.JSX.Element {
  return (
    <div
      role="alert"
      className={`rounded-lg bg-rose-50 border border-rose-200 p-4 text-rose-800 ${className}`}
    >
      <div className="flex items-start space-x-3">
        <AlertCircle className="w-5 h-5 text-rose-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-rose-900">{title}</h4>
          <p className="mt-1 text-xs text-rose-700">{message}</p>
          {onRetry && (
            <div className="mt-3">
              <Button
                variant="danger"
                size="sm"
                onClick={onRetry}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Thử lại
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
