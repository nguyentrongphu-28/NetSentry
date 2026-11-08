# Wireframes (low-fidelity, implemented in `frontend/src/pages`)

## Dashboard
```
+-----------+----------------------------------------------------+
| NetSentry | Dashboard                                          |
| Dashboard | [Devices 1/2] [Open findings 3] [Open high 2] [Open medium 1]
| Devices   | Open findings by severity  critical ▏ 0            |
| Findings  |                            high     ████ 2         |
| Remediat. | Recent scans: device | started | status | dur | n  |
| Audit log |                                                    |
+-----------+----------------------------------------------------+
```
## Devices
```
Hostname | IP | Role | Model/IOS | Connection(+error text) | Last scan | [Test connection][Run scan]
```
## Device detail
```
← Devices   LAB-SW1
[info card]  [Findings on this device]  [Snapshots + From/To compare → diff (+ green / - red)]  [Scan history]
```
## Findings (master/detail)
```
Filters: Severity [all▾] Status [open▾]
+-------------------------------+--------------------------------+
| Rule | Title | Sev | Status   | NS-001 — Telnet enabled        |
| NS-001 ...          (click)   | Evidence (code block)          |
| NS-002 ...                    | Rationale / Remediation guidance|
|                               | [AI explanation] [ask…][Explain]|
+-------------------------------+--------------------------------+
```
## Remediation
```
Stepper: Preview > Approve > Execute > Verify
1. Request: action▾ device▾ params…  [Generate preview]
2. Preview: commands (from template) | validation errors (blocks approval)
   [Approve][Reject][Execute (confirm dialog)][Verify]  → result banner
```
## Audit log
`Time | Actor | Action | Target | Result(success/denied/error) | Detail`

States designed for every screen: loading, empty, error (with Retry).
