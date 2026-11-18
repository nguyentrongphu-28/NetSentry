import { describe, it, expect, vi } from "vitest";
import {
  formatDateTime,
  formatDuration,
  formatRelativeTime,
  SEVERITY_ORDER,
  FINDING_STATUS_ORDER,
} from "./format";

describe("format utilities", () => {
  it("formats date-time string in Vietnamese locale", () => {
    const formatted = formatDateTime("2026-11-18T08:30:00Z");
    expect(formatted).not.toBe("–");
    expect(formatted).toContain("2026");
  });

  it("handles null or empty date gracefully", () => {
    expect(formatDateTime(null)).toBe("–");
    expect(formatDateTime(undefined)).toBe("–");
    expect(formatRelativeTime(null)).toBe("Chưa audit");
  });

  it("formats relative time correctly", () => {
    const now = new Date("2026-11-18T10:00:00Z").getTime();
    vi.setSystemTime(now);

    // 10 seconds ago -> "vừa xong"
    const justNow = new Date("2026-11-18T09:59:50Z").toISOString();
    expect(formatRelativeTime(justNow)).toBe("vừa xong");

    // 10 minutes ago
    const tenMinAgo = new Date("2026-11-18T09:50:00Z").toISOString();
    expect(formatRelativeTime(tenMinAgo)).toContain("10");

    // 2 hours ago
    const twoHoursAgo = new Date("2026-11-18T08:00:00Z").toISOString();
    expect(formatRelativeTime(twoHoursAgo)).toContain("2");

    vi.useRealTimers();
  });

  it("formats duration between two dates correctly", () => {
    expect(
      formatDuration("2026-11-18T08:00:00Z", "2026-11-18T08:00:45Z")
    ).toBe("45s");

    expect(
      formatDuration("2026-11-18T08:00:00Z", "2026-11-18T08:02:15Z")
    ).toBe("2m 15s");

    expect(
      formatDuration("2026-11-18T08:00:00Z", "2026-11-18T08:02:00Z")
    ).toBe("2m");

    expect(formatDuration("invalid", "invalid")).toBe("–");
  });

  it("maintains correct severity priority order", () => {
    expect(SEVERITY_ORDER.CRITICAL).toBeGreaterThan(SEVERITY_ORDER.HIGH);
    expect(SEVERITY_ORDER.HIGH).toBeGreaterThan(SEVERITY_ORDER.MEDIUM);
    expect(SEVERITY_ORDER.MEDIUM).toBeGreaterThan(SEVERITY_ORDER.LOW);
    expect(SEVERITY_ORDER.LOW).toBeGreaterThan(SEVERITY_ORDER.INFO);
  });

  it("maintains correct finding status order: FAIL > UNKNOWN > PASS", () => {
    expect(FINDING_STATUS_ORDER.FAIL).toBeGreaterThan(FINDING_STATUS_ORDER.UNKNOWN);
    expect(FINDING_STATUS_ORDER.UNKNOWN).toBeGreaterThan(FINDING_STATUS_ORDER.PASS);
  });
});
