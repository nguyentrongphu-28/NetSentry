import { describe, expect, it } from "vitest";
import { diffLines } from "./diff";

describe("diffLines", () => {
  it("returns all 'same' for identical input", () => {
    const d = diffLines("a\nb", "a\nb");
    expect(d.every((l) => l.kind === "same")).toBe(true);
  });
  it("detects additions and removals", () => {
    const d = diffLines("a\nb\nc", "a\nx\nc");
    expect(d.filter((l) => l.kind === "remove").map((l) => l.text)).toEqual(["b"]);
    expect(d.filter((l) => l.kind === "add").map((l) => l.text)).toEqual(["x"]);
  });
  it("handles empty-to-content", () => {
    const d = diffLines("", "a");
    expect(d.some((l) => l.kind === "add" && l.text === "a")).toBe(true);
  });
});
