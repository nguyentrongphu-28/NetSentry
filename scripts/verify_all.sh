#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== 1. Environment Verification ==="
.venv/bin/python scripts/check_env.py

echo "=== 2. Offline Corpus Evaluation (Manifest & Accuracy) ==="
.venv/bin/python evaluation/rule_eval.py --split test --check-manifest

echo "=== 3. Security Requirements Matrix Verification (S1-S15) ==="
.venv/bin/python evaluation/security_matrix.py

echo "=== 4. AI Explanation Security Evaluation (Injection Resistance) ==="
.venv/bin/python evaluation/ai_eval.py

echo "=== 5. Backend Full Test Suite (Unit, API, E2E) ==="
source .venv/bin/activate
pytest -q backend/

echo "=== 6. Documentation Consistency & Relative Links Check ==="
.venv/bin/python scripts/check_docs_links.py

echo "=== 7. Frontend Lint ==="
(cd frontend && npm run lint)

echo "=== 8. Frontend Typecheck ==="
(cd frontend && npm run typecheck)

echo "=== 9. Frontend Unit Tests ==="
(cd frontend && npm test -- --run)

echo "=== 10. Frontend Production Build ==="
(cd frontend && npm run build)

echo "=========================================================="
echo "      [ALL CHECKS PASSED] NETSENTRY SYSTEM VERIFIED       "
echo "=========================================================="
