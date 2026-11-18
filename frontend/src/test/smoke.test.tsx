import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

describe("Smoke test", () => {
  it("renders app successfully without crash", async () => {
    render(<App />);
    expect(await screen.findByRole("button", { name: /kết nối/i })).toBeInTheDocument();
  });
});
