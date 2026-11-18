import React from "react";

export type BadgeVariant = "success" | "danger" | "warning" | "info" | "neutral";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: "sm" | "md";
  className?: string;
  icon?: React.ReactNode;
}

export function Badge({
  children,
  variant = "neutral",
  size = "md",
  className = "",
  icon,
}: BadgeProps): React.JSX.Element {
  const variantClasses: Record<BadgeVariant, string> = {
    success: "bg-emerald-50 text-emerald-700 border-emerald-200",
    danger: "bg-rose-50 text-rose-700 border-rose-200",
    warning: "bg-amber-50 text-amber-700 border-amber-200",
    info: "bg-sky-50 text-sky-700 border-sky-200",
    neutral: "bg-gray-100 text-gray-700 border-gray-200",
  };

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-xs font-semibold",
  };

  return (
    <span
      className={`inline-flex items-center space-x-1 rounded-full border ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
    >
      {icon && <span className="flex-shrink-0 mr-1">{icon}</span>}
      <span>{children}</span>
    </span>
  );
}
