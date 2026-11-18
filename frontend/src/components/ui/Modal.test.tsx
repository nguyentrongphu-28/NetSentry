import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Modal } from "./Modal";

function ModalTestHarness(): React.JSX.Element {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div>
      <button id="open-btn" onClick={() => setIsOpen(true)}>
        Mở modal
      </button>
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Tiêu đề modal"
        description="Mô tả modal"
        footer={<button id="confirm-btn">Xác nhận</button>}
      >
        <input id="input-1" placeholder="Input 1" />
        <input id="input-2" placeholder="Input 2" />
      </Modal>
    </div>
  );
}

describe("Modal component (a11y & focus trap)", () => {
  it("renders with correct accessibility attributes", async () => {
    const user = userEvent.setup();
    render(<ModalTestHarness />);

    await user.click(screen.getByText("Mở modal"));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Tiêu đề modal")).toBeInTheDocument();
    expect(screen.getByText("Mô tả modal")).toBeInTheDocument();
  });

  it("closes when pressing Escape key", async () => {
    const user = userEvent.setup();
    render(<ModalTestHarness />);

    await user.click(screen.getByText("Mở modal"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("restores focus to open button after closing", async () => {
    const user = userEvent.setup();
    render(<ModalTestHarness />);

    const openBtn = screen.getByText("Mở modal");
    await user.click(openBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(openBtn);
  });

  it("traps focus inside the modal with Tab and Shift+Tab", async () => {
    const user = userEvent.setup();
    render(<ModalTestHarness />);

    await user.click(screen.getByText("Mở modal"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    const closeBtn = screen.getByLabelText("Đóng hộp thoại");
    const input1 = screen.getByPlaceholderText("Input 1");
    const input2 = screen.getByPlaceholderText("Input 2");
    const confirmBtn = screen.getByText("Xác nhận");

    // Close button should be initially focused as first focusable
    expect(document.activeElement).toBe(closeBtn);

    await user.tab();
    expect(document.activeElement).toBe(input1);

    await user.tab();
    expect(document.activeElement).toBe(input2);

    await user.tab();
    expect(document.activeElement).toBe(confirmBtn);

    // Tab from last element wraps around to first (close button)
    await user.tab();
    expect(document.activeElement).toBe(closeBtn);

    // Shift+Tab from first element wraps around to last (confirm button)
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(confirmBtn);
  });

  it("regression: typing multiple consecutive characters retains focus on input", async () => {
    const user = userEvent.setup();
    render(<ModalTestHarness />);

    await user.click(screen.getByText("Mở modal"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    const input1 = screen.getByPlaceholderText("Input 1");
    await user.click(input1);
    expect(document.activeElement).toBe(input1);

    await user.keyboard("NetSentryAdminUser123");
    expect(input1).toHaveValue("NetSentryAdminUser123");
    expect(document.activeElement).toBe(input1);
  });
});
