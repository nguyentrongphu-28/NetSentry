import {
  AuditRunDetailOut,
  AuditRunListOut,
  AuditRunSummaryOut,
  DeviceListOut,
  DeviceOut,
  DeviceWithLatestAuditOut,
  FindingOut,
  HealthResponse,
} from "../types/api";

export const mockHealth: HealthResponse = {
  status: "ok",
  version: "0.1.0",
};

export const mockAuditSummaryCompleted: AuditRunSummaryOut = {
  id: 101,
  device_id: "Router-Core-01",
  platform: "cisco_ios",
  status: "COMPLETED",
  started_at: "2026-11-18T08:00:00Z",
  finished_at: "2026-11-18T08:00:15Z",
  hostname: "Core-R1",
  error_code: null,
  error_message: null,
  pass_count: 8,
  fail_count: 2,
  unknown_count: 1,
};

export const mockAuditSummaryFailed: AuditRunSummaryOut = {
  id: 102,
  device_id: "Router-Edge-02",
  platform: "cisco_ios",
  status: "FAILED",
  started_at: "2026-11-18T08:10:00Z",
  finished_at: "2026-11-18T08:10:05Z",
  hostname: null,
  error_code: "AUTH_FAILED",
  error_message: "Authentication failed for user admin.",
  pass_count: 0,
  fail_count: 0,
  unknown_count: 0,
};

export const mockDevice1: DeviceWithLatestAuditOut = {
  device_id: "Router-Core-01",
  name: "Core Router 01",
  host: "192.168.1.1",
  port: 22,
  platform: "cisco_ios",
  created_at: "2026-11-17T06:00:00Z",
  updated_at: "2026-11-17T06:00:00Z",
  latest_audit: mockAuditSummaryCompleted,
};

export const mockDevice2: DeviceWithLatestAuditOut = {
  device_id: "Router-Edge-02",
  name: "Edge Router 02",
  host: "192.168.1.2",
  port: 22,
  platform: "cisco_ios",
  created_at: "2026-11-17T07:00:00Z",
  updated_at: "2026-11-17T07:00:00Z",
  latest_audit: mockAuditSummaryFailed,
};

export const mockDeviceUnaudited: DeviceWithLatestAuditOut = {
  device_id: "Router-Branch-03",
  name: "Branch Router 03",
  host: "192.168.2.1",
  port: 2222,
  platform: "cisco_ios",
  created_at: "2026-11-18T00:00:00Z",
  updated_at: "2026-11-18T00:00:00Z",
  latest_audit: null,
};

export const mockDeviceList: DeviceListOut = {
  items: [mockDevice1, mockDevice2, mockDeviceUnaudited],
};

export const mockCreatedDevice: DeviceOut = {
  device_id: "Router-New-04",
  name: "New Router 04",
  host: "192.168.3.1",
  port: 22,
  platform: "cisco_ios",
  created_at: "2026-11-18T08:00:00Z",
  updated_at: "2026-11-18T08:00:00Z",
};

export const mockFindings: FindingOut[] = [
  {
    rule_id: "CISCO-PASS-01",
    title: "Password Encryption",
    severity: "HIGH",
    status: "PASS",
    evidence: ["service password-encryption"],
    rationale: "Passwords should be encrypted in running-config.",
    remediation: "configure terminal\nservice password-encryption",
    verification: "show running-config | include service password-encryption",
    checked_at: "2026-11-18T08:00:05Z",
  },
  {
    rule_id: "CISCO-TELNET-01",
    title: "Telnet Service Disabled",
    severity: "CRITICAL",
    status: "FAIL",
    evidence: ["line vty 0 4", "transport input telnet ssh"],
    rationale: "Telnet sends credentials in plain text.",
    remediation: "configure terminal\nline vty 0 4\ntransport input ssh",
    verification: "show running-config | section line vty",
    checked_at: "2026-11-18T08:00:06Z",
  },
  {
    rule_id: "CISCO-SNMP-01",
    title: "SNMP Community Default",
    severity: "MEDIUM",
    status: "UNKNOWN",
    evidence: ["SNMP service not configured"],
    rationale: "Default SNMP community strings are easily guessed.",
    remediation: "configure terminal\nsnmp-server community <secret> RO",
    verification: "show snmp community",
    checked_at: "2026-11-18T08:00:07Z",
  },
];

export const mockAuditRunDetail: AuditRunDetailOut = {
  summary: mockAuditSummaryCompleted,
  findings: mockFindings,
};

export const mockAuditRunHistory: AuditRunListOut = {
  items: [mockAuditSummaryCompleted, mockAuditSummaryFailed],
  total: 2,
  limit: 20,
  offset: 0,
};
