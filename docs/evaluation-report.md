# Evaluation Report (TEMPLATE — fill with measured values only)

Status: **NOT YET MEASURED.** Numbers below are placeholders to be filled from real runs. Do not publish claims beyond what is measured.

## 1. Environment
| Item | Value |
|---|---|
| Switch model / IOS | _TBD (A)_ |
| Router model / IOS | _TBD (A)_ |
| Backend commit | _TBD_ |
| AI provider / model | _TBD_ |
| Date | _TBD_ |

## 2. Metrics
| Metric | How to measure | Result |
|---|---|---|
| Connection success rate | ≥20 test-connection attempts per device; successes/attempts | _TBD_ |
| Audit duration | mean/max of `ScanRun.duration_seconds` over ≥10 scans | _TBD_ |
| Rule precision / recall | `scripts/eval_rules.py` on labeled good/bad configs (incl. benign cases that must NOT fire) | _TBD_ |
| Diff correctness | change one line → detected; unrelated change → no new finding | _TBD_ |
| Remediation | allowed VLAN/port: preview→approve→execute→verify pass | _TBD_ |
| AI schema-valid rate | `scripts/eval_assistant.py` with real provider | _TBD_ (mock baseline: 6/6) |
| Injection block rate | same script, I01–I06 | _TBD_ (mock baseline: 6/6) |
| Unauthorized actions blocked | test-plan §4 | _TBD_ |

## 3. Known limitations (keep honest)
- Findings are configuration-based; actual exposure/credential strength is not verified.
- Rules cover only the devices/IOS versions tested.
- AI sanitizer is pattern-based and can be evaded; real protection is the architecture (no device access, allowlist, approval).
- Mock-mode UI results do not prove integration with the real backend.
