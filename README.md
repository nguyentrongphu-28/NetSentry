# NetSentry

AI-Assisted Network Configuration Auditing and Remediation Platform.

## Overview

NetSentry is a network security auditing platform designed
to collect device information, inspect configurations,
identify security weaknesses, and provide remediation guidance.

## Initial Scope

- Cisco IOS devices in an authorized PNETLab environment.
- SSH-based read-only information collection.
- Rule-based configuration auditing.
- FastAPI backend.
- Automated tests for security rules.

## Architecture

- Backend: Python, FastAPI
- Device connection: Netmiko
- Rule engine: Python
- Frontend: React + TypeScript (Vite) — see `frontend/`
- AI assistant: provider-agnostic (offline mock by default; free tiers supported) — see `backend/app/assistant/`
- Database: SQLite (planned)

## Project Structure

- backend/app/connectors: device connections
- backend/app/rules: security checks
- backend/app/api: API endpoints
- backend/tests: automated tests
- docs: architecture and documentation

## Development Setup

Create a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies:

    pip install -r backend/requirements.txt

Run the API:

    uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

Run tests:

    PYTHONPATH=backend pytest -v

## Security

- Only audit devices that the team is authorized to access.
- Do not commit passwords, private keys, or raw device configurations.
- Initial device collection is read-only.
- Configuration changes require a separate approval workflow.

## Frontend

    cd frontend
    npm install
    npm run dev          # http://localhost:5173 — mock data by default, no backend needed
    npm test             # unit tests
    npm run build        # typecheck + production build

To use the real API: create `frontend/.env.local` with `VITE_USE_MOCK=false` and run the backend on port 8000 (Vite proxies `/api`).
Pages: Dashboard, Devices, Device detail (snapshots/diff/history), Findings (evidence + AI explain), Remediation (Preview → Approve → Execute → Verify), Audit log.

## AI assistant

The assistant **explains findings only**. It has no SSH access, cannot run commands, and its output is validated (strict schema, no CLI text, allowlisted actions, verified evidence references). Any change still requires the normal approval workflow.

Default provider is an offline mock (free, no key). To use a real model, set in `.env` (see `.env.example`):

    ASSISTANT_PROVIDER=openai_compat
    ASSISTANT_BASE_URL=<OpenAI-compatible endpoint>   # e.g. Gemini, Groq, OpenRouter, or local Ollama
    ASSISTANT_MODEL=<model name>
    ASSISTANT_API_KEY=<key, if the provider needs one>

Evidence is masked for secrets before being sent to any external provider; use a local model (Ollama) if device data must not leave your network.
Evaluate: `PYTHONPATH=backend python scripts/eval_assistant.py`.

## Documentation

- `docs/architecture.md` — diagram and trust boundaries
- `docs/api-contract.md` — API proposal used by the frontend
- `docs/test-plan.md` — automated, manual, AI-safety and lab test plan
- `docs/wireframes.md`, `docs/demo-script.md`, `docs/evaluation-report.md`
- `docs/HANDOFF.md` — status and next steps for continuing work
