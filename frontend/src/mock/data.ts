import type { AuditLogEntry, ConfigSnapshot, Device, Finding, ScanRun } from "../types";

export const devices: Device[] = [
  {
    device_id: "dev-sw1", hostname: "LAB-SW1", ip_address: "10.0.0.11", role: "switch",
    model: "Cisco IOSvL2", ios_version: "15.2(CML_NIGHTLY)", connection_status: "reachable",
    last_scan_at: "2026-11-08T02:10:00Z", last_error: null,
  },
  {
    device_id: "dev-r1", hostname: "LAB-R1", ip_address: "10.0.0.1", role: "router",
    model: "Cisco IOSv", ios_version: "15.9(3)M6", connection_status: "unreachable",
    last_scan_at: "2026-11-07T15:00:00Z",
    last_error: "ConnectionTimeout: TCP connection to 10.0.0.1:22 timed out after 15s",
  },
];

export const scans: ScanRun[] = [
  { scan_id: "scan-3", device_id: "dev-sw1", started_at: "2026-11-08T02:10:00Z", finished_at: "2026-11-08T02:10:07Z", status: "completed", duration_seconds: 7, findings_count: 4, error: null },
  { scan_id: "scan-2", device_id: "dev-sw1", started_at: "2026-11-07T10:00:00Z", finished_at: "2026-11-07T10:00:06Z", status: "completed", duration_seconds: 6, findings_count: 5, error: null },
  { scan_id: "scan-1", device_id: "dev-r1", started_at: "2026-11-07T15:00:00Z", finished_at: null, status: "failed", duration_seconds: null, findings_count: 0, error: "ConnectionTimeout" },
];

export const findings: Finding[] = [
  {
    rule_id: "NS-001", device_id: "dev-sw1", scan_id: "scan-3",
    title: "Telnet enabled on VTY lines", severity: "high",
    evidence: ["line vty 0 4", " transport input telnet ssh"],
    rationale: "Telnet transmits credentials and session data in clear text. The configuration allows it on VTY lines; whether it is actually used was not verified.",
    remediation: "Restrict VTY lines to SSH: 'transport input ssh'.",
    status: "open", checked_at: "2026-11-08T02:10:07Z",
  },
  {
    rule_id: "NS-002", device_id: "dev-sw1", scan_id: "scan-3",
    title: "SSH version 2 not enforced", severity: "medium",
    evidence: ["(no 'ip ssh version 2' line found in running-config)"],
    rationale: "Without an explicit setting the device may accept SSHv1 depending on IOS version.",
    remediation: "Configure 'ip ssh version 2'.",
    status: "open", checked_at: "2026-11-08T02:10:07Z",
  },
  {
    rule_id: "NS-003", device_id: "dev-sw1", scan_id: "scan-3",
    title: "SNMP community 'public' configured", severity: "high",
    evidence: ["snmp-server community public RO"],
    rationale: "A well-known default community string matches the configuration. This is a suspicious configuration, not a verified exposed service.",
    remediation: "Remove the community or replace it with a unique string restricted by ACL; prefer SNMPv3.",
    status: "open", checked_at: "2026-11-08T02:10:07Z",
  },
  {
    rule_id: "NS-005", device_id: "dev-sw1", scan_id: "scan-3",
    title: "Unused access port not shut down", severity: "low",
    evidence: ["interface GigabitEthernet0/3", " switchport mode access", " (no 'shutdown')"],
    rationale: "Port is 'down' but administratively enabled. Check the baseline before treating this as a vulnerability.",
    remediation: "If the port is unused per baseline, apply 'shutdown'.",
    status: "accepted", checked_at: "2026-11-08T02:10:07Z",
  },
  {
    rule_id: "NS-004", device_id: "dev-sw1", scan_id: "scan-2",
    title: "No login banner configured", severity: "info",
    evidence: ["(no 'banner login' line found)"],
    rationale: "A legal banner is a policy recommendation, not a vulnerability.",
    remediation: "Configure 'banner login' per policy.",
    status: "resolved", checked_at: "2026-11-07T10:00:06Z",
  },
];

const cfgA = `hostname LAB-SW1
!
vlan 10
 name USERS
!
interface GigabitEthernet0/1
 switchport mode access
 switchport access vlan 10
!
interface GigabitEthernet0/3
 switchport mode access
!
snmp-server community public RO
!
line vty 0 4
 transport input telnet ssh
!
end`;

const cfgB = `hostname LAB-SW1
!
vlan 10
 name USERS
vlan 20
 name GUESTS
!
interface GigabitEthernet0/1
 switchport mode access
 switchport access vlan 10
!
interface GigabitEthernet0/3
 switchport mode access
!
snmp-server community public RO
!
banner login ^C Authorized use only ^C
!
line vty 0 4
 transport input telnet ssh
!
end`;

export const snapshots: ConfigSnapshot[] = [
  { snapshot_id: "snap-2", device_id: "dev-sw1", taken_at: "2026-11-08T02:10:05Z", line_count: cfgB.split("\n").length, content: cfgB },
  { snapshot_id: "snap-1", device_id: "dev-sw1", taken_at: "2026-11-07T10:00:04Z", line_count: cfgA.split("\n").length, content: cfgA },
];

export const auditLogs: AuditLogEntry[] = [
  { log_id: "log-3", at: "2026-11-08T02:10:07Z", actor: "analyst", action: "scan.run", target: "dev-sw1", result: "success", detail: "4 findings" },
  { log_id: "log-2", at: "2026-11-07T15:00:20Z", actor: "analyst", action: "device.test_connection", target: "dev-r1", result: "error", detail: "ConnectionTimeout" },
  { log_id: "log-1", at: "2026-11-07T10:05:00Z", actor: "viewer", action: "remediation.execute", target: "dev-sw1", result: "denied", detail: "role 'viewer' lacks permission" },
];
