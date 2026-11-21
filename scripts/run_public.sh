#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
# --no-proxy-headers: keep request.client = the real socket peer (127.0.0.1 from cloudflared),
# so only CF-Connecting-IP (trusted only from loopback) is used for the client IP.
exec uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers
