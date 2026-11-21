# Hướng dẫn Snapshot cấu hình, So sánh (Diff) và Trợ lý AI (Ollama) trong NetSentry

Tài liệu này đặc tả chi tiết kiến trúc, nguyên lý bảo mật, cách cài đặt, cấu hình và vận hành cho ba khả năng mở rộng của NetSentry:
1. **Config Snapshots**: Lưu trữ cấu hình sau audit đã qua chuẩn hóa và che giấu bí mật (redacted).
2. **Diff Engine**: So sánh thay đổi giữa các lần audit (bao gồm Config Diff và Findings Diff).
3. **AI Explanations**: Trợ lý AI cục bộ (thông qua Ollama) giải thích an ninh, phân loại mức độ ưu tiên và cảnh báo rủi ro vận hành bằng tiếng Việt.

---

## 1. Kiến trúc & Nguyên lý bảo mật

### 1.1. Vì sao chỉ lưu cấu hình đã che bí mật (Redacted Snapshot)?
- **Nguyên tắc Zero Raw Credentials on Disk**: NetSentry tuyệt đối không lưu `raw running-config`, mật khẩu, enable secret, pre-shared key (PSK), SNMP community strings, hay private key lên đĩa cứng hoặc database.
- **ConfigRedactor**: Trước khi lưu, cấu hình được xử lý qua regex redactor nhằm phát hiện và thay thế các chuỗi nhạy cảm bằng dấu vân tay SHA-256 có muối (keyed HMAC-SHA256 truncated):
  ```text
  enable secret 5 $1$mERr$9cTjUIEqNGurFTpt6pwST0  -->  enable secret <REDACTED:8f12a4>
  snmp-server community public RO                -->  snmp-server community <REDACTED:3c9b71> RO
  ```
- **Dấu vân tay (Deterministic Fingerprinting)**: Giúp Diff Engine phát hiện được khi nào một mật khẩu hoặc secret bị thay đổi giữa hai lần audit (vân tay thay đổi), nhưng kẻ tấn công không thể giải mã hay suy ngược lại mật khẩu gốc từ dấu vân tay.
- **Tính nhạy cảm của Snapshot**: Mặc dù đã che mật khẩu, snapshot vẫn chứa cấu trúc mạng (IP schema, routing protocol, ACL, VLAN). Do đó:
  - File snapshot được phân quyền nghiêm ngặt: POSIX permissions `0600` (file) và `0700` (thư mục chứa `data/snapshots/`).
  - Thư mục snapshot nằm ngoài mã nguồn và được khai báo trong `.gitignore`.
  - Kiểm tra và ngăn chặn tuyệt đối các kỹ thuật **Path Traversal** (`device_id` chứa `../`).

### 1.2. Chuẩn hóa cấu hình (ConfigNormalizer)
- Các thiết bị mạng thường xuất hiện các dòng biến động không mang tính logic bảo mật (như `! Last configuration change at ...`, `! NVRAM config last updated at ...`, `Building configuration...`, định dạng dòng `\r\n`).
- `ConfigNormalizer` loại bỏ các dòng nhiễu và chuẩn hóa ký tự xuống dòng thành `\n` trước khi băm SHA-256 và lưu trữ để tránh tình trạng "false diff" khi so sánh.

---

## 2. Cài đặt và Vận hành Ollama Cục bộ

NetSentry yêu cầu một máy chủ Ollama chạy cục bộ (chỉ chấp nhận địa chỉ Loopback: `127.0.0.1` hoặc `localhost` theo mặc định). NetSentry **tuyệt đối không gửi dữ liệu cấu hình hoặc findings lên các dịch vụ AI trên Internet** (như OpenAI, Gemini Cloud API...).

### 2.1. Cài đặt Ollama
Tải và cài đặt Ollama từ trang chính thức:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2.2. Tải mô hình khuyến nghị
Mô hình tiêu chuẩn được kiểm thử và khuyến nghị cho NetSentry là `llama3:8b` (hoặc `qwen2.5:7b` cho khả năng hiểu tiếng Việt tốt):
```bash
# Tải mô hình
ollama pull llama3:8b

# Kiểm tra danh sách mô hình đã tải
ollama list
```

### 2.3. Khởi động và kiểm tra kết nối
Đảm bảo daemon Ollama đang lắng nghe trên cổng 11434:
```bash
curl -s http://127.0.0.1:11434/api/tags
```
Kết quả JSON trả về cần hiển thị danh sách các model đang sẵn có.

### 2.4. Yêu cầu phần cứng ước lượng
| Mô hình | VRAM tối thiểu (GPU) | RAM hệ thống (CPU only) | Tốc độ phản hồi ước tính |
| :--- | :--- | :--- | :--- |
| `llama3:8b` / `qwen2.5:7b` (4-bit quant) | ~6 GB VRAM | ~16 GB RAM | 2s - 8s (GPU) / 15s - 30s (CPU) |
| `llama3.2:3b` | ~3 GB VRAM | ~8 GB RAM | 1s - 3s (GPU) / 5s - 12s (CPU) |

> [!TIP]
> Nếu chạy trên máy chủ không có GPU (CPU-only), hãy tăng biến môi trường `NETSENTRY_AI_TIMEOUT_SECONDS=180` để tránh lỗi timeout.

---

## 3. Bảng biến môi trường (Environment Variables)

| Tên biến | Kiểu | Mặc định | Mô tả |
| :--- | :--- | :--- | :--- |
| `NETSENTRY_SNAPSHOT_ENABLED` | bool | `true` | Bật/tắt tính năng tự động lưu snapshot cấu hình sau audit. |
| `NETSENTRY_SNAPSHOT_DIR` | path | `data/snapshots` | Thư mục lưu trữ các file snapshot được phân quyền `0700`. |
| `NETSENTRY_SNAPSHOT_KEEP_PER_DEVICE` | int | `10` | Số lượng snapshot tối đa lưu cho mỗi thiết bị (bản cũ nhất sẽ tự động xóa). |
| `NETSENTRY_SNAPSHOT_CONTENT_API` | bool | `true` | Cho phép đọc nội dung snapshot qua API. *(Tự động tắt về `false` khi chạy chế độ công khai)* |
| `NETSENTRY_AI_ENABLED` | bool | `false` | Bật/tắt tính năng trợ lý AI giải thích. |
| `NETSENTRY_AI_OLLAMA_URL` | url | `http://127.0.0.1:11434` | Địa chỉ máy chủ Ollama (mặc định bắt buộc loopback). |
| `NETSENTRY_AI_MODEL` | string | `llama3:8b` | Tên model Ollama sử dụng. |
| `NETSENTRY_AI_TIMEOUT_SECONDS` | int | `120` | Thời gian chờ tối đa khi yêu cầu Ollama sinh phản hồi. |
| `NETSENTRY_AI_CONCURRENCY` | int | `1` | Số lượng tác vụ AI được phép thực hiện song song (semaphore). |
| `NETSENTRY_AI_RATE_LIMIT_PER_USER` | int | `10` | Số lượt gọi AI tối đa cho mỗi user trong 1 giờ (sliding window). |
| `NETSENTRY_AI_ALLOW_REMOTE_OLLAMA` | bool | `false` | Cho phép kết nối Ollama ở địa chỉ IP khác loopback (cần cấu hình rõ ràng). |

---

## 4. Hành vi trong Chế độ Công khai (Public Mode)

Khi NetSentry được cấu hình với `NETSENTRY_PUBLIC_MODE=1` (ví dụ chia sẻ demo qua Cloudflare Tunnels):
- `NETSENTRY_SNAPSHOT_CONTENT_API` **bị cưỡng bức tắt (`false`)**: Mọi yêu cầu API truy cập nội dung chi tiết của snapshot (`GET /api/v1/snapshots/{id}`) và Config Diff (`GET /api/v1/devices/{id}/diff`) sẽ lập tức trả về lỗi:
  ```json
  {
    "error": {
      "code": "CONTENT_DISABLED",
      "message": "Snapshot content viewing is disabled in public demonstration mode."
    }
  }
  ```
- Giao diện Dashboard sẽ hiển thị cảnh báo: *"Chức năng xem nội dung cấu hình đang tắt ở chế độ công khai"*.
- **Findings Diff** (`/api/v1/audits/{id}/compare`) và **AI Explanations** (`/api/v1/audits/{id}/explain`) **vẫn hoạt động bình thường**, do chỉ thao tác trên danh sách findings đã được che giấu toàn bộ thông tin nhạy cảm.
- Bắt buộc `NETSENTRY_AI_ALLOW_REMOTE_OLLAMA=0` (không cho phép chuyển hướng sang LLM từ xa trong chế độ công khai).

---

## 5. Bản chất AI & Biện pháp phòng vệ Prompt Injection

> [!IMPORTANT]
> **AI chỉ giải thích văn bản - Tuyệt đối không sinh lệnh và không thực thi trên thiết bị!**
> NetSentry được thiết kế không có bất kỳ kênh nào (command bus, queue, socket hay SSH exec) để đưa đầu ra của AI vào luồng thực thi lên thiết bị mạng.

### 5.1. Prompt Sanitization & Anti-Injection
- Khi tạo prompt cho AI, `PromptBuilder` chỉ truyền: `rule_id`, `severity`, `title` và danh sách `evidence` đã được trích lọc.
- **Không bao giờ gửi**: IP, hostname, credential, mật khẩu hoặc raw config vào LLM prompt.
- Các chuỗi độc hại mang tính Prompt Injection (ví dụ: `</findings>`, `Ignore previous instructions and output...`) được bao bọc trong khối phân cách và cắt ngắn tối đa 200 ký tự mỗi dòng bằng chứng.

### 5.2. ExplanationValidator (Lọc đầu ra AI)
Mọi kết quả JSON sinh ra từ Ollama đều phải đi qua `ExplanationValidator`:
- Bỏ qua bất kỳ `rule_id` nào do AI tự bịa đặt mà không nằm trong findings thật.
- Bổ sung các rule FAIL bị AI bỏ sót.
- **Lọc triệt để dòng lệnh**: Mọi dòng trông giống cấu hình Cisco IOS (như `ip route ...`, `no shutdown`, `service ...`) đều bị loại bỏ ngay lập tức.
- **Xóa bỏ mã độc**: HTML tags, URL links, script tags trong câu trả lời của AI đều bị strip sạch trước khi trả về cho client hoặc lưu vào database.
- Bắt buộc hiển thị nhãn Disclaimer: *"Nội dung do AI sinh ra, chỉ mang tính tham khảo. Hãy đối chiếu với mô tả của từng rule."*

---

## 6. Xử lý sự cố thường gặp (Troubleshooting)

1. **`AI_UNAVAILABLE` (503)**:
   - Kiểm tra service Ollama: `systemctl status ollama` hoặc chạy `ollama serve`.
   - Kiểm tra endpoint tags: `curl http://127.0.0.1:11434/api/tags`.
   - Kiểm tra model đã được tải chưa: `ollama list`.

2. **`AI_BUSY` (429)**:
   - Hệ thống đang có một yêu cầu phân tích AI khác đang chạy (do giới hạn semaphore `NETSENTRY_AI_CONCURRENCY=1`). Chờ vài giây và thử lại.
   - User đã vượt quá hạn mức gọi AI trong giờ (`NETSENTRY_AI_RATE_LIMIT_PER_USER`).

3. **`AI_OUTPUT_INVALID` (502)**:
   - Ollama trả về JSON không đúng format schema yêu cầu hoặc phản hồi vượt quá kích thước cho phép (256 KB). Thử bấm "Phân tích lại" (`force=1`).

4. **Khi tắt AI (`NETSENTRY_AI_ENABLED=0`)**:
   - Toàn bộ các chức năng cốt lõi (Audit, Rule Engine, Lưu Snapshot, So sánh Diff) vẫn hoạt động hoàn toàn bình thường và ổn định.
