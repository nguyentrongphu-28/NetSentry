# Cấu hình chuẩn (Baseline) và Phát hiện Lệch chuẩn (Drift Detection) trong NetSentry

Tài liệu này mô tả chi tiết tính năng quản lý cấu hình chuẩn (Baseline) và phát hiện lệch cấu hình (Configuration Drift) trong hệ thống kiểm toán an ninh mạng thiết bị NetSentry.

---

## 1. Khái niệm Baseline (Cấu hình chuẩn)

### 1.1 Baseline là gì?
Baseline trong NetSentry là một bản snapshot cấu hình thiết bị (đã được làm sạch, che thông tin nhạy cảm và chuẩn hóa) được người quản trị (`admin`) phê duyệt chính thức làm chuẩn mực hoạt động an toàn của thiết bị đó.

Mỗi thiết bị mạng tại một thời điểm chỉ có tối đa **một** baseline ở trạng thái hoạt động (`ACTIVE`).

### 1.2 Khi nào nên duyệt Baseline?
- **Thời điểm tốt nhất:** Ngay sau khi thiết bị được đưa vào vận hành hoặc sau khi đã hoàn thành một lượt audit mà toàn bộ các quy tắc an ninh đều vượt qua (số lỗi `FAIL = 0`).
- **Trường hợp có lỗi FAIL:** Nếu snapshot chứa lỗi bảo mật (`FAIL > 0`), hệ thống mặc định từ chối duyệt (`409 BASELINE_FAILURES_NOT_CONFIRMED`) nhằm ngăn chặn việc vô tình biến một cấu hình có lỗ hổng thành chuẩn mực. Quản trị viên chỉ có thể duyệt khi tích chọn xác nhận rõ ràng (`confirm_with_failures = true`), đồng thời số lỗi FAIL tại thời điểm duyệt sẽ được ghi lại trong hồ sơ (`fail_count_at_approval`) để phục vụ kiểm toán sau này.
- **Ai có quyền duyệt:** Chỉ người dùng có vai trò `admin` mới có quyền phê duyệt (`POST /devices/{id}/baseline`) hoặc gỡ bỏ (`DELETE /devices/{id}/baseline`) baseline.

### 1.3 Cơ chế vòng đời và giao dịch
- Khi quản trị viên duyệt một snapshot mới làm baseline, giao dịch cơ sở dữ liệu sẽ tự động chuyển baseline `ACTIVE` hiện tại (nếu có) sang trạng thái `RETIRED` (ghi nhận `retired_at`, `retired_by`) và kích hoạt bản mới.
- Quá trình này diễn ra nguyên khối trong một transaction (`BEGIN IMMEDIATE`), không để lại trạng thái dở dang.
- Lịch sử tất cả các lần duyệt và gỡ bỏ baseline được lưu giữ đầy đủ tại bảng `baselines` và có thể tra cứu qua `GET /devices/{id}/baselines`.

### 1.4 Cơ chế bảo vệ và ghim Snapshot (Snapshot Pinning)
- Snapshot đang được liên kết với một baseline `ACTIVE` sẽ được hệ thống "ghim" (`is_pinned = true`).
- Snapshot được ghim **không bao giờ bị xóa** bởi chính sách xoay vòng lưu trữ định kỳ (`NETSENTRY_SNAPSHOT_KEEP`), và không bị tính vào giới hạn số lượng snapshot lưu giữ.
- Mọi yêu cầu xóa thủ công snapshot đang làm baseline (`DELETE /api/v1/snapshots/{id}`) sẽ bị chặn với mã lỗi `409 SNAPSHOT_IN_USE`.
- Khi baseline chuyển sang `RETIRED`, snapshot liên quan sẽ không còn bị ghim và có thể được dọn dẹp theo chính sách lưu trữ thông thường.

---

## 2. Cách tính toán Drift (Phát hiện lệch chuẩn)

### 2.1 Nguyên tắc tính toán
Drift được tính toán hoàn toàn ngoại tuyến từ hai bản snapshot đã được che bí mật và chuẩn hóa:
1. Snapshot của baseline `ACTIVE`.
2. Snapshot của lượt audit đang kiểm tra.

Hệ thống **không thực hiện thêm kết nối SSH** nào tới thiết bị và không can thiệp vào cấu hình đang chạy trên thiết bị mạng.

### 2.2 Tách khối cấu hình (`config_blocks.py`)
Cấu hình thiết bị (Cisco IOS) được bóc tách theo cấu trúc khối logic:
- **Khối có con (Block with children):** Tiêu đề khối không thụt đầu dòng (như `interface GigabitEthernet0/1`, `line vty 0 4`, `ip access-list extended MGMT`, `router ospf 1`), theo sau bởi các lệnh con có thụt lề. Toàn bộ các dòng con giữ nguyên thứ tự nghiêm ngặt (đặc biệt quan trọng với ACL vì thứ tự đánh giá quyết định chính sách an ninh).
- **Dòng toàn cục đơn lẻ (Global commands):** Các lệnh độc lập một dòng (như `hostname`, `service password-encryption`, `ip domain-name`) được gom vào khối giả `(global)`. Khối này được so sánh theo tập hợp dòng (thêm/xóa dòng, không phụ thuộc thứ tự xuất hiện trong file cấu hình).
- **Khối Banner nhiều dòng:** Đoạn `banner <type> <delimiter> ... <delimiter>` được coi là một khối thống nhất, không để các dòng nội dung banner bị lọt vào khối `(global)`.
- **Lọc bỏ nhiễu:** Dòng chú thích (`!`), dòng trống, và từ khóa `end` được tự động loại bỏ. Các khối trùng tiêu đề được gộp nội dung theo thứ tự xuất hiện.

### 2.3 Phân loại thay đổi (Change Classification)
- `ADDED`: Khối chỉ xuất hiện ở cấu hình hiện tại mà không có trong baseline.
- `REMOVED`: Khối chỉ có trong baseline nhưng đã bị xóa khỏi cấu hình hiện tại.
- `CHANGED`: Khối xuất hiện ở cả hai nơi nhưng có sự khác biệt về nội dung dòng (sử dụng thuật toán `difflib.ndiff` để xác định dòng thêm `+` và dòng bớt `-`).

### 2.4 Cờ liên quan bảo mật (`security_relevant`)
Một khối hoặc thay đổi được tự động gắn cờ `security_relevant = true` nếu tiêu đề khối bắt đầu bằng các tiền tố an ninh quan trọng:
- Quản lý truy cập: `line vty`, `line con`, `line aux`, `aaa`, `username`, `enable`.
- Giao thức quản trị & dịch vụ: `snmp-server`, `ip ssh`, `ip http`, `ntp authentication`, `logging`, `service`.
- Kiểm soát lưu lượng & mã hóa: `access-list`, `ip access-list`, `crypto`, `banner`.

Đối với khối `(global)`, nếu bất kỳ dòng thêm hoặc xóa nào bắt đầu bằng các tiền tố trên, khối cũng sẽ được đánh dấu liên quan bảo mật. Các khối này luôn được ưu tiên hiển thị đầu danh sách để thu hút sự chú ý của quản trị viên.

### 2.5 Tính toán tự động sau Audit
Trong quy trình chạy audit (`AuditRunService`), ngay sau khi snapshot được tạo thành công:
- Nếu thiết bị có baseline `ACTIVE`, hệ thống tự động tính toán bản tóm tắt drift và lưu vào bảng `drift_results`.
- Quá trình này được bao bọc trong khối xử lý ngoại lệ an toàn: nếu có lỗi phát sinh trong lúc so sánh drift, lỗi chỉ được ghi vào nhật ký cảnh báo và **không bao giờ làm thất bại lượt audit**.

---

## 3. Giới hạn đã biết (Known Limitations)

1. **Không so sánh ngữ nghĩa (Semantic-Agnostic):** Hệ thống so sánh cú pháp theo khối và dòng ký tự, không phân tích ngữ nghĩa của lệnh. Ví dụ, một lệnh toàn cục đổi giá trị như `ip ssh version 1` thành `ip ssh version 2` sẽ được ghi nhận là 1 dòng bị xóa và 1 dòng được thêm trong khối `(global)`, chứ không phải là hành động "sửa giá trị".
2. **Cắt bớt cấu hình lớn (`DRIFT_MAX_BLOCKS`):** Để đảm bảo hiệu năng và tránh quá tải bộ nhớ/băng thông mạng, số lượng khối thay đổi tối đa được trả về trong một báo cáo drift được giới hạn bởi cấu hình `NETSENTRY_DRIFT_MAX_BLOCKS` (mặc định 500 khối). Nếu vượt quá, báo cáo sẽ được gắn cờ `truncated: true`.
3. **Phụ thuộc vào mức độ che bí mật:** Drift chỉ phản ánh những gì xuất hiện trong snapshot đã được che. Vì mọi mật khẩu và secret đã được thay thế an toàn bằng dấu vân tay `<REDACTED:xxxxxx>` (sử dụng HMAC-SHA256 với khóa bí mật hệ thống), nên khi mật khẩu trên thiết bị thay đổi, dấu vân tay sẽ thay đổi và dòng đó được đánh dấu là thay đổi mà **tuyệt đối không làm lộ giá trị mật khẩu thật**.

---

## 4. Hành vi ở Chế độ Công khai (`NETSENTRY_PUBLIC_MODE=1`)

Khi hệ thống vận hành ở chế độ công khai (môi trường demo hoặc internet mở):
- Báo cáo drift mức **tóm tắt** (`GET /devices/{id}/drift?detail=0`) và **lịch sử drift** (`GET /devices/{id}/drift/history`) vẫn hoạt động bình thường, cho phép người dùng quan sát tổng số khối lệch chuẩn, tên các khối và cờ bảo mật.
- Yêu cầu xem **chi tiết dòng cấu hình** (`GET /devices/{id}/drift?detail=1`) sẽ bị chặn với mã lỗi `403 Forbidden` (`code: CONTENT_DISABLED`), tương ứng với chính sách vô hiệu hóa API xem nội dung cấu hình (`NETSENTRY_SNAPSHOT_CONTENT_API=0`).
- Giao diện người dùng sẽ hiển thị thông báo rõ ràng: *"Xem dòng cấu hình đang tắt ở chế độ công khai."*

---

## 5. Mối liên hệ với các giai đoạn tiếp theo (Tự động sửa lỗi / Remediation)

Trong các phiên bản nâng cấp tiếp theo của NetSentry (Remediation C, D):
- Khi hệ thống thực thi kế hoạch sửa lỗi tự động được quản trị viên phê duyệt (ví dụ: tắt `ip http server` hoặc bật `service password-encryption`), cấu hình trên thiết bị sẽ thay đổi và dẫn đến tình trạng **lệch baseline có chủ đích**.
- Khi đó, lượt audit xác minh sau sửa lỗi sẽ ghi nhận trạng thái `DRIFTED`.
- Quản trị viên sau khi xác minh cấu hình mới đã khắc phục toàn bộ lỗ hổng và vận hành ổn định cần thực hiện thao tác **phê duyệt baseline mới** từ snapshot vừa cập nhật để đưa hệ thống trở lại trạng thái `IN_SYNC`.
