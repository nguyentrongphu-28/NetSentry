# HANDOFF — Member C (Frontend, AI, QA/Docs)

> Written for the next engineer or AI agent continuing Member C's work. Read this first.
> Last updated: see `git log docs/HANDOFF.md`. Branch: `feat/member-c-frontend-ai-qa`.

## 1. Source of truth
- Plan: `NetSentry_AI_3_Person_8_Week_Implementation_Plan.docx` (3 members, 8 weeks). Member C = Frontend + AI assistant + QA/Docs.
- Repo state when C started: only FastAPI skeleton (`/`, `/health`), `backend/app/connectors/ssh_connector.py` (Netmiko), `scripts/test_cisco_connection.py`. No DB, no API, no rules engine.
- Everything C built works WITHOUT the real backend (mock mode) so C is never blocked by A/B.

## 2. Status checklist (update this as you go)
Legend: [x] done and tested, [~] partial, [ ] not started

### Week 1 — wireframes, mock data, test plan
- [x] Wireframes → `docs/wireframes.md`
- [x] Mock data → `frontend/src/mock/data.ts`
- [x] Initial test plan → `docs/test-plan.md`
### Week 2-3 — layout, devices, detail
- [x] Layout/nav, Dashboard, Devices (test connection + scan buttons, error display), Device detail (snapshots, findings, scan history)
### Week 4-5 — findings, diff, audit
- [x] Findings table + severity/status filters + evidence/rationale/remediation panel
- [x] Snapshot diff viewer (LCS line diff, unit-tested), Audit log page
### Week 6 — remediation UI
- [x] Wizard: parameters → preview → validation errors → approve/reject → execute (confirm dialog) → verify
- [~] Works against MOCK only. Needs real endpoints from B (see §5).
### Week 7 — AI assistant
- [x] `backend/app/assistant/` (schemas, sanitizer, prompts, providers, service, router) + 42 pytest tests (39 assistant + 3 eval metrics); frontend: 9 vitest tests (diff + mock workflow rules)
- [x] Frontend `AiExplain` panel on findings page
- [ ] Not tested against a real free LLM provider (no key available in dev sandbox). Mock provider only.
### Week 8 — docs, evaluation
- [x] README, architecture, API contract proposal, test plan, demo script, evaluation template
- [ ] Video demo and slides: need humans + real lab. Script is in `docs/demo-script.md`.
- [ ] Measured numbers (precision/recall, audit time, connection success): need A's rules + real devices. Harness: `scripts/eval_rules.py`, `scripts/eval_assistant.py`.

## 3. How to run
```bash
# Frontend (mock mode, no backend needed)
cd frontend && npm install && npm run dev        # http://localhost:5173
npm test && npm run build                        # vitest + typecheck + production build

# Backend tests (from repo root)
pip install -r backend/requirements.txt
PYTHONPATH=backend pytest -v

# Run API
uvicorn app.main:app --app-dir backend --port 8000
# Frontend against real API: set VITE_USE_MOCK=false in frontend/.env.local (vite proxies /api -> :8000)
```

## 4. Files owned by C
- `frontend/**`
- `backend/app/assistant/**`, `backend/tests/assistant/**`
- `docs/{HANDOFF,architecture,api-contract,wireframes,test-plan,demo-script,evaluation-report}.md`
- `scripts/eval_rules.py`, `scripts/eval_assistant.py`, `tests/qa/**`
- One-line edit in `backend/app/main.py`: `app.include_router(assistant_router)` (B owns this file — keep it a one-liner).

## 5. Open dependencies on A and B (the real integration gaps)
1. **B must implement the endpoints in `docs/api-contract.md`.** It is a PROPOSAL derived from plan §5.1 plus extras the UI needs: `GET /api/devices/{id}`, `GET /api/devices/{id}/scans`, `GET /api/devices/{id}/snapshots`, `GET /api/devices/{id}/findings`, `GET /api/audit-logs`, `POST /api/remediations/{id}/reject`. If B's contract differs, edit ONLY `frontend/src/api/client.ts` (`realApi`) and `frontend/src/types/index.ts`.
2. **B must add RBAC + audit log to `/api/assistant/explain`** (marked `NOTE (B)` in `router.py`).
3. **Allowlist sync:** `ALLOWED_ACTIONS` in `assistant/schemas.py` and param validators in `assistant/service.py` mirror the remediation allowlist. B/A must keep them in sync; B's validation is authoritative (assistant check is defense-in-depth only).
4. **A:** rule IDs in `mock/data.ts` and `_MOCK_KB` in `providers.py` (NS-001..NS-005) are placeholders. Replace with A's real rule IDs/evidence format.
5. **Uplink protection** is a hard-coded `UPLINKS = ["Gi0/0"]` in the mock only. Real enforcement must be in B's backend.

## 6. Decisions made (and why)
- **Vite + React + TS, plain CSS, no UI lib**: fewer deps, easy to review. README said React+TS.
- **Mock-first**: `VITE_USE_MOCK` defaults to true; mock enforces the same workflow rules (cannot execute unapproved job, etc.) so UI behaviour is realistic.
- **AI provider**: abstraction with `mock` (default, offline) and `openai_compat` (works with Gemini free tier, Groq free tier, OpenRouter `:free` models, local Ollama). Uses stdlib `urllib` → no new runtime dependency. Config via env: `ASSISTANT_PROVIDER`, `ASSISTANT_BASE_URL`, `ASSISTANT_API_KEY`, `ASSISTANT_MODEL` (see `.env.example`).
- **LLM output is untrusted**: strict Pydantic schema (`extra=forbid`), CLI-in-text rejected, evidence refs must exist, suggested params re-validated, injection in question blocked BEFORE model call, injection lines/secrets stripped from evidence before prompt.
- AI never gets SSH, never executes; a proposal is only a hint the user can turn into a normal Preview job.

## 7. Known issues / risks to tell the human
- `.myvenv/` (≈3,700 files) is committed to `main` — `.gitignore` only lists `.venv/`. Recommend: add `.myvenv/` to `.gitignore` and `git rm -r --cached .myvenv`. NOT done by C (shared repo hygiene; needs team agreement).
- `ssh_connector.py` hard-codes `/root/.ssh/config` and `use_keys=False` (A's file; not touched).
- `backend/requirements.txt` is a full `pip freeze` (includes uvloop etc.). C only appended `httpx==0.28.1` (needed by FastAPI TestClient for tests).
- Frontend has no auth/login UI yet (plan says RBAC "nếu cần"). When B adds auth, add a login page + token in `http()` in `client.ts`.
- Mock `diff`/`snapshots` only cover `dev-sw1`.
- `npm audit` reports advisories in dev tooling (vite/vitest dev deps); not run-time. Review before release.

## 8. Next steps for whoever continues (priority order)
1. Pull B's real API; switch `VITE_USE_MOCK=false`; fix contract mismatches in `client.ts`.
2. Try the AI with a real free provider (see README → "AI assistant"); record results in `docs/evaluation-report.md`.
3. Run `scripts/eval_assistant.py` with the real provider; record schema-valid %, injection-block %.
4. Once A's rules exist, create labeled cases in `sample-data/eval/cases.json` and run `scripts/eval_rules.py --runner <module:function>`.
5. Run the manual QA matrix in `docs/test-plan.md` on the lab; fill in results.
6. Record the demo using `docs/demo-script.md`; take screenshots.

## 9. Delivery note
C had no push access to GitHub. Work is on local branch `feat/member-c-frontend-ai-qa` and delivered as `netsentry-member-c.patch` (git format-patch) + zip. Apply with: `git checkout -b feat/member-c-frontend-ai-qa && git am netsentry-member-c.patch`, then `git push -u origin feat/member-c-frontend-ai-qa` and open a PR (needs review from A or B per plan §3).
