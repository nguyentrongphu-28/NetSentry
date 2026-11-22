#!/usr/bin/env bash
# ==============================================================================
# NetSentry - All-in-One One-Click Launcher (Production / Public Cloudflare Mode)
# ==============================================================================
# Tự động:
# 1. Kiểm tra môi trường (Python 3.12, venv, packages, frontend build)
# 2. Khởi tạo admin nếu database chưa có
# 3. Kích hoạt Backend chế độ Public Mode (tự phục vụ Frontend SPA chung origin)
# 4. Mở Cloudflare Quick Tunnel ra Internet và in URL truy cập
# 5. Dọn dẹp an toàn khi tắt (Ctrl+C)
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Màu hiển thị
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}       NetSentry - One-Click Launcher (Cisco Lab + Cloudflare)   ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Kiểm tra môi trường ảo
if [ ! -d ".venv" ]; then
    echo -e "${RED}[ERROR] Không tìm thấy thư mục .venv! Hãy tạo môi trường ảo trước:${NC}"
    echo "  python3.12 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
    exit 1
fi

source .venv/bin/activate

# 2. Kiểm tra frontend dist (Nếu chưa build thì tự build)
if [ ! -f "frontend/dist/index.html" ]; then
    echo -e "${YELLOW}[*] Chưa tìm thấy frontend/dist, đang tiến hành build Frontend...${NC}"
    (cd frontend && npm install && npm run build)
fi

# 3. Nạp cấu hình từ .env nếu có
if [ -f "backend/.env" ]; then
    echo -e "${GREEN}[*] Đang nạp cấu hình từ backend/.env...${NC}"
    set -a
    source backend/.env
    set +a
fi

# 4. Thiết lập các biến môi trường bắt buộc cho Public & Tunnel Mode
export NETSENTRY_PUBLIC_MODE=1
export NETSENTRY_SERVE_FRONTEND=1
export NETSENTRY_TRUSTED_IP_HEADER="CF-Connecting-IP"
export NETSENTRY_DB_PATH="${NETSENTRY_DB_PATH:-netsentry.db}"
export NETSENTRY_ENABLE_DOCS=0
export NETSENTRY_SNAPSHOT_CONTENT_API=0
export NETSENTRY_REMEDIATION_EXECUTE_MODE="${NETSENTRY_REMEDIATION_EXECUTE_MODE:-live}"

# Dải mạng thiết bị Cisco Lab mặc định nếu chưa cấu hình (chống SSRF)
export NETSENTRY_ALLOWED_NETWORKS="${NETSENTRY_ALLOWED_NETWORKS:-192.168.1.0/24,10.0.0.0/8,172.16.0.0/12}"

# 5. Khởi tạo cơ sở dữ liệu & tài khoản Admin ban đầu nếu chưa có
echo -e "${GREEN}[*] Kiểm tra tài khoản quản trị (Admin)...${NC}"
python3 - << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, "backend")
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.repositories.database import init_db
from app.core.config import Settings
from app.security.password_hasher import Argon2PasswordHasher
from app.domain.entities.user import Role

db_path = Path("backend") / "netsentry.db"
init_db(db_path)
repo = SQLiteUserRepository(db_path)
if repo.count_active_admins() == 0:
    hasher = Argon2PasswordHasher()
    default_pass = "AdminNetSentry2026!"
    repo.add("admin", hasher.hash(default_pass), Role.ADMIN, must_change_password=False)
    print(f"\n>>> [TẠO ADMIN MẶC ĐỊNH THÀNH CÔNG] Username: admin | Password: {default_pass}\n")
EOF

# 6. Kiểm tra cloudflared binary
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}[ERROR] Không tìm thấy 'cloudflared' trong PATH!${NC}"
    echo "Hãy cài đặt bằng: curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null"
    exit 1
fi

TUNNEL_LOG="/tmp/netsentry_tunnel.log"
rm -f "$TUNNEL_LOG"

# Dọn dẹp tiến trình khi bấm Ctrl+C hoặc thoát script
cleanup() {
    echo -e "\n${YELLOW}[*] Đang dừng Backend và Cloudflare Tunnel...${NC}"
    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "${TUNNEL_PID:-}" ]; then
        kill "$TUNNEL_PID" 2>/dev/null || true
    fi
    rm -f "$TUNNEL_LOG"
    echo -e "${GREEN}[OK] Đã dọn dẹp xong. Tạm biệt!${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 7. Khởi động Backend (bind loopback 127.0.0.1:8000)
echo -e "${GREEN}[*] Khởi động NetSentry Backend (Port 8000)...${NC}"
cd backend
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers &
BACKEND_PID=$!
cd ..

# Đợi Backend sẵn sàng
echo -e "${YELLOW}[*] Đợi Backend khởi động...${NC}"
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}[OK] Backend đã sẵn sàng!${NC}"
        break
    fi
    sleep 0.5
done

# 8. Khởi động Cloudflare Quick Tunnel
echo -e "${GREEN}[*] Đang tạo Cloudflare Tunnel công khai...${NC}"
cloudflared tunnel --url http://127.0.0.1:8000 > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

# Đợi tìm URL public từ cloudflared
PUBLIC_URL=""
for i in {1..60}; do
    if [ -f "$TUNNEL_LOG" ]; then
        URL=$(grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -n 1 || true)
        if [ -n "$URL" ]; then
            PUBLIC_URL="$URL"
            break
        fi
    fi
    sleep 0.5
done

echo ""
echo -e "${BLUE}================================================================${NC}"
if [ -n "$PUBLIC_URL" ]; then
    echo -e "${GREEN}>>> NETSENTRY ĐANG CHẠY CÔNG KHAI TẠI:${NC}"
    echo -e "${YELLOW}    ${PUBLIC_URL}${NC}"
    echo -e "${GREEN}>>> Tài khoản quản trị:${NC} admin"
    echo -e "${GREEN}>>> Mật khẩu khởi tạo: ${NC} AdminNetSentry2026! (hoặc mật khẩu bạn đã đổi)"
else
    echo -e "${RED}[!] Không bắt được URL Cloudflare. Hãy kiểm tra $TUNNEL_LOG${NC}"
fi
echo -e "${BLUE}================================================================${NC}"
echo -e "${YELLOW}[*] Nhấn Ctrl+C để dừng toàn bộ hệ thống.${NC}"
echo ""

# Giữ script chạy để theo dõi log
wait "$BACKEND_PID"
