import React from "react";

export interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
}

export function Card({
  children,
  className = "",
  title,
  subtitle,
  action,
}: CardProps): React.JSX.Element {
  return (
    <div
      className={`bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden ${className}`}
    >
      {(title || action) && (
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            {title && (
              <h3 className="text-base font-semibold text-gray-900 leading-6">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-gray-500 leading-4">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex-shrink-0">{action}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
