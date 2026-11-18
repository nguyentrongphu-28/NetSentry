import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import fs from "node:fs";
import path from "node:path";
import { StatusBadge } from "../components/audits/StatusBadge";
import { SeverityBadge } from "../components/audits/SeverityBadge";

function getAppSourceFiles(dir: string, fileList: string[] = []): string[] {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      if (file === "test") continue; // Exclude test harness directory
      getAppSourceFiles(fullPath, fileList);
    } else if (/\.(ts|tsx)$/.test(file) && !file.includes(".test.")) {
      fileList.push(fullPath);
    }
  }
  return fileList;
}

describe("Security and Accessibility Audits (Section 7.8 - 7.9)", () => {
  it("never uses dangerouslySetInnerHTML in application source code (Section 7.8)", () => {
    const srcDir = path.resolve(__dirname, "..");
    const files = getAppSourceFiles(srcDir);
    const offenders: string[] = [];

    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      if (content.includes("dangerouslySetInnerHTML")) {
        offenders.push(path.relative(srcDir, file));
      }
    }

    expect(offenders).toEqual([]);
  });

  it("never uses localStorage in application source code (Section 7.9)", () => {
    const srcDir = path.resolve(__dirname, "..");
    const files = getAppSourceFiles(srcDir);
    const offenders: string[] = [];

    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, idx) => {
        const trimmed = line.trim();
        if (
          trimmed.includes("localStorage") &&
          !trimmed.startsWith("//") &&
          !trimmed.startsWith("*")
        ) {
          offenders.push(`${path.relative(srcDir, file)}:${idx + 1}`);
        }
      });
    }

    expect(offenders).toEqual([]);
  });

  it("never exposes API keys in VITE_ environment variables or source files (Section 7.9)", () => {
    const envExamplePath = path.resolve(__dirname, "../../.env.example");
    if (fs.existsSync(envExamplePath)) {
      const envContent = fs.readFileSync(envExamplePath, "utf-8");
      expect(envContent).not.toMatch(/VITE_.*API_KEY/i);
    }

    const srcDir = path.resolve(__dirname, "..");
    const files = getAppSourceFiles(srcDir);
    const offenders: string[] = [];

    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      if (/import\.meta\.env\.VITE_.*KEY/i.test(content)) {
        offenders.push(path.relative(srcDir, file));
      }
    }

    expect(offenders).toEqual([]);
  });

  it("StatusBadge and SeverityBadge always render visible text for accessibility (Section 7.8)", () => {
    const { rerender } = render(<StatusBadge status="PASS" />);
    expect(screen.getByText("PASS")).toBeInTheDocument();

    rerender(<StatusBadge status="FAIL" />);
    expect(screen.getByText("FAIL")).toBeInTheDocument();

    rerender(<StatusBadge status="UNKNOWN" />);
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();

    rerender(<SeverityBadge severity="CRITICAL" />);
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();

    rerender(<SeverityBadge severity="HIGH" />);
    expect(screen.getByText("HIGH")).toBeInTheDocument();

    rerender(<SeverityBadge severity="MEDIUM" />);
    expect(screen.getByText("MEDIUM")).toBeInTheDocument();

    rerender(<SeverityBadge severity="LOW" />);
    expect(screen.getByText("LOW")).toBeInTheDocument();

    rerender(<SeverityBadge severity="INFO" />);
    expect(screen.getByText("INFO")).toBeInTheDocument();
  });
});
