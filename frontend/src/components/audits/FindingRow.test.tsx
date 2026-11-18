import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FindingRow } from "./FindingRow";
import { FindingOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";

const mockFinding: FindingOut = {
  rule_id: "CISCO-PASSWORD-01",
  title: "Service password-encryption is not enabled",
  severity: "MEDIUM",
  status: "FAIL",
  rationale: "Passwords should be encrypted in configuration files.",
  remediation: "configure terminal\nservice password-encryption",
  evidence: ["no service password-encryption"],
  verification: "show running-config | include password-encryption",
};

describe("FindingRow copy remediation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("successfully copies remediation string to clipboard and shows copied status", async () => {
    const user = userEvent.setup();
    const writeTextSpy = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined);

    render(<FindingRow finding={mockFinding} />);

    // Expand finding row first
    const expandButton = screen.getByRole("button", {
      name: new RegExp(mockFinding.rule_id, "i"),
    });
    await user.click(expandButton);

    // Initial role="status" exists and is empty
    const statusRegion = screen.getByRole("status");
    expect(statusRegion).toBeInTheDocument();
    expect(statusRegion).toHaveTextContent("");

    // Click copy remediation button
    const copyButton = screen.getByRole("button", {
      name: STRINGS.auditDetail.copyRemediation,
    });
    await user.click(copyButton);

    expect(writeTextSpy).toHaveBeenCalledTimes(1);
    expect(writeTextSpy).toHaveBeenCalledWith(mockFinding.remediation);
    expect(statusRegion).toHaveTextContent(STRINGS.auditDetail.copied);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("displays error message and does NOT show copied state when Promise is rejected", async () => {
    const user = userEvent.setup();
    const writeTextSpy = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockRejectedValue(new Error("Clipboard permission denied"));

    render(<FindingRow finding={mockFinding} />);

    // Expand finding row
    const expandButton = screen.getByRole("button", {
      name: new RegExp(mockFinding.rule_id, "i"),
    });
    await user.click(expandButton);

    const statusRegion = screen.getByRole("status");
    expect(statusRegion).toHaveTextContent("");

    // Click copy remediation button
    const copyButton = screen.getByRole("button", {
      name: STRINGS.auditDetail.copyRemediation,
    });
    await user.click(copyButton);

    expect(writeTextSpy).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      STRINGS.auditDetail.copyFailed
    );
    expect(statusRegion).toHaveTextContent("");
    expect(
      screen.queryByText(STRINGS.auditDetail.copied)
    ).not.toBeInTheDocument();
  });

  it("displays error message and does not crash when navigator.clipboard does not exist", async () => {
    const user = userEvent.setup();
    const originalClipboard = navigator.clipboard;

    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      configurable: true,
      writable: true,
    });

    try {
      render(<FindingRow finding={mockFinding} />);

      // Expand finding row
      const expandButton = screen.getByRole("button", {
        name: new RegExp(mockFinding.rule_id, "i"),
      });
      await user.click(expandButton);

      const statusRegion = screen.getByRole("status");
      expect(statusRegion).toHaveTextContent("");

      // Click copy button
      const copyButton = screen.getByRole("button", {
        name: STRINGS.auditDetail.copyRemediation,
      });
      await user.click(copyButton);

      expect(screen.getByRole("alert")).toHaveTextContent(
        STRINGS.auditDetail.copyFailed
      );
      expect(statusRegion).toHaveTextContent("");
      expect(
        screen.queryByText(STRINGS.auditDetail.copied)
      ).not.toBeInTheDocument();
    } finally {
      Object.defineProperty(navigator, "clipboard", {
        value: originalClipboard,
        configurable: true,
        writable: true,
      });
    }
  });
});
