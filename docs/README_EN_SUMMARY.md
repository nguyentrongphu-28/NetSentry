# NetSentry: Executive Summary & Project Overview

NetSentry is an enterprise-grade automated security auditing and safe remediation platform designed for network infrastructure running Cisco IOS, fully compliant with the CIS Cisco IOS Benchmark.

---

## 1. Problem Statement & Motivation
Network misconfigurations on core routing and switching hardware represent one of the most critical attack surfaces in enterprise environments. Weak authentication protocols (Telnet cleartext, weak enable passwords), disabled encryption, open web administration interfaces, and unrestricted VTY lines expose organizations to credential theft, eavesdropping, and remote compromise. Manual security audits are infrequent, error-prone, and lack verification safeguards during remediation.

---

## 2. Solution & Core Capabilities

- **Automated CIS Benchmark Auditing**:
  Evaluates running configurations against 8 essential CIS rules (NET-001 through NET-008) using an offline, in-memory Abstract Syntax Tree (AST) engine capable of evaluating configs in under 1 millisecond.
- **Snapshot Versioning & Drift Detection**:
  Maintains cryptographically masked configuration snapshots using HMAC-SHA256 redaction to prevent secret leakage, tracking unauthorized drift against established golden baselines.
- **AI-Powered Risk Explanation with Zero Command Injection**:
  Integrates a local Ollama Large Language Model (Qwen 2.5) to translate technical findings into actionable risk assessments in natural language. By architectural design, **the AI is strictly confined to explanatory duties and is fundamentally prohibited from generating CLI commands**, neutralizing indirect prompt injection vectors.
- **Safe Remediation with Four-Eyes Governance**:
  Implements a rigorous Maker-Checker workflow: operators propose remediation plans based on verified static templates, while a distinct administrator must approve them via step-up re-authentication.
- **Automated Verification & Reversible Rollback**:
  Applies changes via dedicated, allowlisted write connectors, executes immediate independent verification audits, and triggers automatic rollback if the target state is not achieved.

---

## 3. Security Engineering & Verification Highlights

NetSentry enforces defense-in-depth across 15 core security requirements (S1 through S15) validated by 47 automated test nodes:
- **Zero Secret Leakage**: Passwords, tokens, and community strings are scrubbed from database entries, audit findings, events, and API responses.
- **RBAC & CSRF Protection**: Strict role segregation (Viewer, Operator, Admin) combined with Origin validation on all state-modifying requests.
- **Tamper Detection**: State machine CAS atomic locks and cryptographic plan hashing (`plan_hash`) detect any unauthorized modifications between approval and application.
- **Public Mode Hardening**: Safe exposure via Cloudflare Quick Tunnel with disabled documentation endpoints, blocked raw configuration access, and enforced authentication invariants.

---

## 4. Key Performance Metrics
- **Rule Precision, Recall & F1**: **100.0%** across frozen test corpus configs (`MANIFEST.sha256`).
- **Security Matrix Pass Rate**: **47 / 47 tests passed (0 GAPs)**.
- **Prompt Injection Resistance**: **20 / 20 malicious injection scenarios neutralized**.
- **Offline Engine Throughput**: Median latency of **0.115 ms** per configuration evaluation.
