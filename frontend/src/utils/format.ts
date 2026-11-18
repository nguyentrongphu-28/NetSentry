import { FindingSeverity, FindingStatus, AuditRunStatus } from "../types/api";

const dateTimeFormatter = new Intl.DateTimeFormat("vi-VN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

const relativeTimeFormatter = new Intl.RelativeTimeFormat("vi", {
  numeric: "auto",
});

/**
 * Format ISO datetime string to localized Vietnamese format: DD/MM/YYYY, HH:mm:ss
 */
export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "–";
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return dateTimeFormatter.format(date);
  } catch {
    return dateStr;
  }
}

/**
 * Format ISO datetime string to relative time in Vietnamese (e.g. "vừa xong", "5 phút trước", "2 giờ trước")
 */
export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "Chưa audit";
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;

    const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
    const absDiff = Math.abs(diffSeconds);

    if (absDiff < 60) {
      return "vừa xong";
    }

    const diffMinutes = Math.round(diffSeconds / 60);
    if (Math.abs(diffMinutes) < 60) {
      return relativeTimeFormatter.format(diffMinutes, "minute");
    }

    const diffHours = Math.round(diffMinutes / 60);
    if (Math.abs(diffHours) < 24) {
      return relativeTimeFormatter.format(diffHours, "hour");
    }

    const diffDays = Math.round(diffHours / 24);
    if (Math.abs(diffDays) < 30) {
      return relativeTimeFormatter.format(diffDays, "day");
    }

    const diffMonths = Math.round(diffDays / 30);
    if (Math.abs(diffMonths) < 12) {
      return relativeTimeFormatter.format(diffMonths, "month");
    }

    const diffYears = Math.round(diffDays / 365);
    return relativeTimeFormatter.format(diffYears, "year");
  } catch {
    return dateStr;
  }
}

/**
 * Format duration between two ISO dates into human-readable string (e.g., "15s", "1m 20s")
 */
export function formatDuration(startStr: string, endStr: string): string {
  try {
    const start = new Date(startStr).getTime();
    const end = new Date(endStr).getTime();
    if (isNaN(start) || isNaN(end) || end < start) {
      return "–";
    }

    const totalSeconds = Math.round((end - start) / 1000);
    if (totalSeconds < 60) {
      return `${totalSeconds}s`;
    }

    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
  } catch {
    return "–";
  }
}

/**
 * Severity priority ordering for sorting. Higher number = higher priority.
 */
export const SEVERITY_ORDER: Record<FindingSeverity, number> = {
  CRITICAL: 5,
  HIGH: 4,
  MEDIUM: 3,
  LOW: 2,
  INFO: 1,
};

/**
 * Finding status priority ordering for sorting.
 * Default sort requirement: FAIL -> UNKNOWN -> PASS
 */
export const FINDING_STATUS_ORDER: Record<FindingStatus, number> = {
  FAIL: 3,
  UNKNOWN: 2,
  PASS: 1,
};

/**
 * Audit run status order
 */
export const RUN_STATUS_ORDER: Record<AuditRunStatus, number> = {
  COMPLETED: 2,
  FAILED: 1,
};
