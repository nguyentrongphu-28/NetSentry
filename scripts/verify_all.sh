#!/usr/bin/env bash
set -euo pipefail

echo "=== Backend tests ==="
source .venv/bin/activate
pytest -q backend/

echo "=== Frontend lint ==="
(cd frontend && npm run lint)

echo "=== Frontend typecheck ==="
(cd frontend && npm run typecheck)

echo "=== Frontend tests ==="
(cd frontend && npm test -- --runInBand)

echo "=== Build frontend ==="
(cd frontend && npm run build)

echo "=== Verification complete ==="
