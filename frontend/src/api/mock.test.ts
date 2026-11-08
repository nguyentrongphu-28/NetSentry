import { describe, expect, it } from "vitest";
import { mockApi } from "./mock";

const vlan = (id: string, name = "GUESTS") =>
  mockApi.previewRemediation({ action_type: "create_vlan", target_device: "dev-sw1", params: { vlan_id: id, vlan_name: name } });

describe("mock remediation workflow", () => {
  it("valid VLAN produces template preview", async () => {
    const j = await vlan("20");
    expect(j.preview).toEqual(["vlan 20", " name GUESTS"]);
    expect(j.validation_errors).toEqual([]);
  });
  it("invalid VLAN id and injected name produce validation errors and no preview", async () => {
    const a = await vlan("5000");
    const b = await vlan("20", "A\nreload");
    expect(a.validation_errors.length).toBeGreaterThan(0);
    expect(a.preview).toEqual([]);
    expect(b.validation_errors.length).toBeGreaterThan(0);
  });
  it("cannot approve a job with validation errors", async () => {
    const j = await vlan("1");
    await expect(mockApi.approveRemediation(j.job_id)).rejects.toThrow(/validation/);
  });
  it("cannot execute before approval or verify before execute", async () => {
    const j = await vlan("30");
    await expect(mockApi.executeRemediation(j.job_id)).rejects.toThrow(/not approved/);
    await expect(mockApi.verifyRemediation(j.job_id)).rejects.toThrow(/not executed|Nothing to verify/);
  });
  it("happy path: approve → execute → verify", async () => {
    const j = await vlan("40");
    await mockApi.approveRemediation(j.job_id);
    await mockApi.executeRemediation(j.job_id);
    const v = await mockApi.verifyRemediation(j.job_id);
    expect(v.verification_result?.passed).toBe(true);
  });
  it("blocks uplink port and unknown action", async () => {
    const u = await mockApi.previewRemediation({ action_type: "configure_access_port", target_device: "dev-sw1", params: { interface: "Gi0/0", vlan_id: "10" } });
    expect(u.validation_errors.join()).toMatch(/uplink/);
    await expect(mockApi.previewRemediation({ action_type: "erase_flash" as never, target_device: "dev-sw1", params: {} })).rejects.toThrow(/allowlist/);
  });
});
