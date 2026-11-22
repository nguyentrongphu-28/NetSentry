#!/usr/bin/env bash
# ==============================================================================
# NetSentry - Hardened One-Click Launcher (Production / Public Cloudflare Mode)
# ==============================================================================
# Tự động:
# 1. Kiểm tra môi trường ảo ($VIRTUAL_ENV hoặc .venv) và thư viện (argon2, netmiko, paramiko)
# 2. Thư mục dữ liệu & SQLite tách biệt hoàn toàn ngoài mã nguồn (quyền 700)
# 3. Ép buộc khai báo NETSENTRY_ALLOWED_NETWORKS (chống SSRF)
# 4. Kiểm tra tài khoản admin: nếu chưa có, yêu cầu nhập bằng getpass (không lộ pass)
# 5. Kích hoạt Backend chế độ Public Mode (tự phục vụ Frontend SPA chung origin)
#    - EXECUTE_MODE cố định là 'off' (chế độ công khai cấm thực thi sửa đổi)
# 6. Kiểm tra /health trước khi mở Cloudflare Quick Tunnel ra Internet
# 7. Thẩm định an toàn sau khi mở tunnel (/docs 404, /api/v1/devices 401)
# 8. Dọn dẹp an toàn khi tắt (Ctrl+C)
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
echo -e "${BLUE}       NetSentry - Hardened Launcher (Cisco Lab + Cloudflare)   ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Kiểm tra môi trường ảo Python
VENV_DIR=""
if [ -n "${VIRTUAL_ENV:-}" ] && [ -d "$VIRTUAL_ENV" ]; then
    VENV_DIR="$VIRTUAL_ENV"
elif [ -d "$REPO_ROOT/.venv" ]; then
    VENV_DIR="$REPO_ROOT/.venv"
else
    echo -e "${RED}[ERROR] Không tìm thấy môi trường ảo Python! Vui lòng kích hoạt venv hoặc tạo .venv:${NC}"
    echo "  python3.12 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
    exit 1
fi

PYTHON_BIN="$VENV_DIR/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    echo -e "${RED}[ERROR] Không tìm thấy python binary tại: $PYTHON_BIN${NC}"
    exit 1
fi

# 2. Kiểm tra các thư viện bắt buộc (argon2, netmiko, paramiko) và phiên bản
echo -e "${GREEN}[*] Kiểm tra thư viện cốt lõi...${NC}"
MISSING_LIB=""
if ! "$PYTHON_BIN" -c "import argon2" >/dev/null 2>&1; then
    MISSING_LIB="argon2"
elif ! "$PYTHON_BIN" -c "import netmiko" >/dev/null 2>&1; then
    MISSING_LIB="netmiko"
elif ! "$PYTHON_BIN" -c "import paramiko" >/dev/null 2>&1; then
    MISSING_LIB="paramiko"
fi

if [ -n "$MISSING_LIB" ]; then
    echo -e "${RED}[ERROR] Thiếu thư viện '$MISSING_LIB' trong môi trường ảo!${NC}"
    echo "Hãy chạy: pip install -r backend/requirements.txt"
    exit 1
fi

# Kiểm tra phiên bản netmiko (hỗ trợ 4.8.0 hoặc 3.4.0) và paramiko (hỗ trợ 5.1.0 hoặc 3.5.x / 3.4.0 cho Cisco cũ)
VER_NETMIKO="$("$PYTHON_BIN" -c "import importlib.metadata; print(importlib.metadata.version('netmiko'))")"
VER_PARAMIKO="$("$PYTHON_BIN" -c "import importlib.metadata; print(importlib.metadata.version('paramiko'))")"
if [[ "$VER_NETMIKO" != "4.8.0" && "$VER_NETMIKO" != "3.4.0" ]] || [[ "$VER_PARAMIKO" != "5.1.0" && "$VER_PARAMIKO" != "3.5.1" && "$VER_PARAMIKO" != "3.5.0" && "$VER_PARAMIKO" != "3.4.0" ]]; then
    echo -e "${RED}[ERROR] Phiên bản thư viện mạng không đúng yêu cầu an toàn!${NC}"
    echo "  Yêu cầu: netmiko in (4.8.0, 3.4.0), paramiko in (5.1.0, 3.5.1, 3.5.0, 3.4.0)"
    echo "  Hiện tại: netmiko==$VER_NETMIKO, paramiko==$VER_PARAMIKO"
    exit 1
fi
echo -e "${GREEN}[OK] Thư viện mạng hợp lệ: netmiko==$VER_NETMIKO, paramiko==$VER_PARAMIKO, argon2 OK.${NC}"

# 3. Kiểm tra frontend dist
if [ ! -f "frontend/dist/index.html" ]; then
    echo -e "${YELLOW}[*] Chưa tìm thấy frontend/dist, đang tiến hành build Frontend...${NC}"
    (cd frontend && npm install && npm run build)
fi

# 4. Nạp cấu hình từ .env nếu có
if [ -f "backend/.env" ]; then
    echo -e "${GREEN}[*] Đang nạp cấu hình từ backend/.env...${NC}"
    set -a
    source backend/.env
    set +a
fi

# 5. Thư mục dữ liệu & Database (Đặt tuyệt đối ngoài mã nguồn)
DATA_DIR="${NETSENTRY_DATA_DIR:-$HOME/netsentry-data}"
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"

export NETSENTRY_DB_PATH="${NETSENTRY_DB_PATH:-$DATA_DIR/netsentry.db}"
REAL_REPO_PATH="$(cd "$REPO_ROOT" && pwd -P)"
REAL_DB_DIR="$(dirname "$(realpath -m "$NETSENTRY_DB_PATH")")"
if [[ "$REAL_DB_DIR" == "$REAL_REPO_PATH"* ]]; then
    echo -e "${YELLOW}[CẢNH BÁO] Cơ sở dữ liệu ($NETSENTRY_DB_PATH) đang nằm trong thư mục repo! Khuyến nghị đặt ngoài repo qua NETSENTRY_DATA_DIR.${NC}"
fi

# 6. Thiết lập các biến môi trường bắt buộc cho Public & Tunnel Mode
export NETSENTRY_PUBLIC_MODE=1
export NETSENTRY_SERVE_FRONTEND=1
export NETSENTRY_TRUSTED_IP_HEADER="CF-Connecting-IP"
export NETSENTRY_ENABLE_DOCS=0
export NETSENTRY_SNAPSHOT_CONTENT_API=0

# Chế độ công khai cấm thực thi sửa đổi; muốn thử sửa cấu hình thật phải chạy KHÔNG công khai qua SSH tunnel.
export NETSENTRY_REMEDIATION_EXECUTE_MODE="off"

# Bắt buộc khai báo ALLOWED_NETWORKS (chống SSRF), không có mặc định rộng
if [ -z "${NETSENTRY_ALLOWED_NETWORKS:-}" ]; then
    if [ -t 0 ]; then
        echo -e "${YELLOW}[!] NETSENTRY_ALLOWED_NETWORKS chưa được đặt.${NC}"
        read -rp "Nhập IP hoặc dải mạng router Cisco (ví dụ: 192.168.1.1/32): " USER_INPUT_NETWORKS
        USER_INPUT_NETWORKS="$(echo "$USER_INPUT_NETWORKS" | tr -d '[:space:]')"
        if [ -n "$USER_INPUT_NETWORKS" ]; then
            # Tự động thêm /32 nếu người dùng chỉ nhập IP đơn lẻ (không có /)
            if [[ "$USER_INPUT_NETWORKS" != *"/"* ]]; then
                USER_INPUT_NETWORKS="${USER_INPUT_NETWORKS}/32"
            fi
            export NETSENTRY_ALLOWED_NETWORKS="$USER_INPUT_NETWORKS"
        fi
    fi
fi
: "${NETSENTRY_ALLOWED_NETWORKS:?Hãy đặt NETSENTRY_ALLOWED_NETWORKS = IP router, ví dụ 192.168.1.1/32}"

# Nhập tài khoản SSH kết nối router Cisco (chế độ công khai bảo vệ chống lộ pass qua web)
if [ -z "${NETSENTRY_SSH_USERNAME:-}" ] && [ -t 0 ]; then
    echo -e "${GREEN}[*] Cấu hình tài khoản SSH kết nối Cisco Router:${NC}"
    read -rp "  Nhập SSH Username của router [mặc định: admin]: " USER_SSH_NAME
    USER_SSH_NAME="${USER_SSH_NAME:-admin}"
    export NETSENTRY_SSH_USERNAME="$USER_SSH_NAME"

    read -rsp "  Nhập SSH Password của router: " USER_SSH_PASS
    echo ""
    export NETSENTRY_SSH_PASSWORD="$USER_SSH_PASS"

    read -rsp "  Nhập Enable Secret của router (bỏ trống nếu không có): " USER_SSH_SECRET
    echo ""
    if [ -n "$USER_SSH_SECRET" ]; then
        export NETSENTRY_ENABLE_SECRET="$USER_SSH_SECRET"
    fi
fi



# 7. Kiểm tra tài khoản quản trị (Admin)
echo -e "${GREEN}[*] Kiểm tra tài khoản quản trị (Admin)...${NC}"
HAS_ADMIN="$("$PYTHON_BIN" - << 'EOF'
import sys
from pathlib import Path
import os
sys.path.insert(0, "backend")
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.repositories.database import init_db

db_path = Path(os.environ["NETSENTRY_DB_PATH"])
init_db(db_path)
repo = SQLiteUserRepository(db_path)
print("1" if repo.count_active_admins() > 0 else "0")
EOF
)"

if [ "$HAS_ADMIN" != "1" ]; then
    echo -e "${YELLOW}[!] Cơ sở dữ liệu chưa có tài khoản Admin nào.${NC}"
    if [ -t 0 ]; then
        echo -e "${YELLOW}[*] Đang khởi tạo tài khoản Admin lần đầu (nhập mật khẩu an toàn qua getpass):${NC}"
        "$PYTHON_BIN" backend/scripts/create_admin.py --username admin
    else
        echo -e "${RED}[ERROR] Cần khởi tạo tài khoản Admin trước khi khởi động ở chế độ phi tương tác!${NC}"
        echo "Hãy chạy lệnh sau trên terminal để tạo tài khoản admin:"
        echo "  export NETSENTRY_DB_PATH=\"$NETSENTRY_DB_PATH\""
        echo "  python backend/scripts/create_admin.py --username admin"
        exit 1
    fi
fi

# 8. Kiểm tra cloudflared binary
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}[ERROR] Không tìm thấy 'cloudflared' trong PATH!${NC}"
    echo "Hãy cài đặt bằng: curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null"
    exit 1
fi

TUNNEL_LOG="$DATA_DIR/tunnel.log"
BACKEND_LOG="$DATA_DIR/backend.log"
touch "$BACKEND_LOG" "$TUNNEL_LOG"
chmod 600 "$BACKEND_LOG" "$TUNNEL_LOG"

BACKEND_PID=""
TUNNEL_PID=""

# Dọn dẹp tiến trình khi bấm Ctrl+C hoặc thoát script
cleanup() {
    echo -e "\n${YELLOW}[*] Đang dừng Backend và Cloudflare Tunnel...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$TUNNEL_PID" ]; then
        kill "$TUNNEL_PID" 2>/dev/null || true
    fi
    rm -f "$TUNNEL_LOG"
    echo -e "${GREEN}[OK] Đã dọn dẹp xong. Tạm biệt!${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 9. Khởi động Backend (bind loopback 127.0.0.1:8000)
echo -e "${GREEN}[*] Khởi động NetSentry Backend (Port 8000)...${NC}"
(
    cd backend
    "$PYTHON_BIN" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers >> "$BACKEND_LOG" 2>&1
) &
BACKEND_PID=$!

# Đợi Backend sẵn sàng và kiểm tra sống còn
echo -e "${YELLOW}[*] Đợi Backend khởi động...${NC}"
BACKEND_READY=0
for i in {1..30}; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "${RED}[ERROR] Backend đã bị dừng đột ngột! 40 dòng log cuối:${NC}"
        tail -n 40 "$BACKEND_LOG" || true
        exit 1
    fi

    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
        BACKEND_READY=1
        echo -e "${GREEN}[OK] Backend đã sẵn sàng!${NC}"
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" -ne 1 ]; then
    echo -e "${RED}[ERROR] Backend không phản hồi /health sau 30 giây! 40 dòng log cuối:${NC}"
    tail -n 40 "$BACKEND_LOG" || true
    exit 1
fi

# 10. Khởi động Cloudflare Quick Tunnel (CHỈ khi /health đã OK)
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

if [ -z "$PUBLIC_URL" ]; then
    echo -e "${RED}[ERROR] Không bắt được URL Cloudflare từ $TUNNEL_LOG!${NC}"
    tail -n 20 "$TUNNEL_LOG" || true
    exit 1
fi

# 11. Thẩm định an toàn sau khi có URL Tunnel
echo -e "${GREEN}[*] Thẩm định an toàn endpoints sau khởi động...${NC}"
CODE_DOCS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/openapi.json || echo "000")
CODE_DEVICES=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/devices || echo "000")

if [ "$CODE_DOCS" != "404" ]; then
    echo -e "${RED}[ERROR] Vi phạm an ninh: /openapi.json trả về mã $CODE_DOCS (kỳ vọng 404)!${NC}"
    exit 1
fi

if [ "$CODE_DEVICES" != "401" ]; then
    echo -e "${RED}[ERROR] Vi phạm an ninh: /api/v1/devices trả về mã $CODE_DEVICES (kỳ vọng 401)!${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Thẩm định an ninh đạt chuẩn: /openapi.json (404), /api/v1/devices (401).${NC}"

echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}>>> NETSENTRY ĐANG CHẠY CÔNG KHAI TẠI:${NC}"
echo -e "${YELLOW}    ${PUBLIC_URL}${NC}"
echo -e "${GREEN}>>> Tài khoản quản trị:${NC} admin"
echo -e "${BLUE}================================================================${NC}"
echo -e "${YELLOW}[*] Nhấn Ctrl+C để dừng toàn bộ hệ thống.${NC}"
echo ""

# Giữ script chạy để theo dõi log
wait "$BACKEND_PID"
