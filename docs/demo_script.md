# Kịch Bản Trình Diễn Hệ Thống (Demo Script)

Kịch bản demo có thời lượng 8–10 phút, phân định rõ ràng các bước thao tác, nội dung trình bày, những gì hiển thị trên màn hình và kịch bản dự phòng nếu router lab gặp sự cố.

---

## 1. Phân Bổ Thời Gian & Vai Trò Trình Bày

- **Thời lượng**: 8–10 phút.
- **Người thực hiện**:
  - **Người thuyết trình (Speaker)**: Giới thiệu bối cảnh, giải thích kiến trúc và biện pháp bảo mật.
  - **Người thao tác (Operator)**: Thao tác trực tiếp trên giao diện web NetSentry và terminal đối chứng.

---

## 2. Kịch Bản Chi Tiết Từng Phút (Timeline)

### Đoạn 1: Bối cảnh, Đặt vấn đề & Tổng quan (Phút 0:00 – 1:30)
- **Lời thoại**: "Xin chào thầy cô và các bạn. Trong quản trị mạng doanh nghiệp, cấu hình sai sót trên thiết bị định tuyến là nguyên nhân hàng đầu dẫn đến rò rỉ dữ liệu và xâm nhập mạng. NetSentry được phát triển nhằm tự động hóa việc kiểm toán tuân thủ chuẩn CIS Benchmark cho thiết bị Cisco IOS, tích hợp cơ chế khắc phục an toàn theo nguyên tắc kiểm soát 4 mắt (Four-Eyes Principle)."
- **Hành động**: Chiếu slide kiến trúc tổng thể và mở màn hình Đăng nhập NetSentry.

### Đoạn 2: Đăng nhập Operator & Chạy Kiểm Toán (Phút 1:30 – 3:30)
- **Lời thoại**: "Đầu tiên, quản trị viên vận hành `demo_operator` đăng nhập vào hệ thống. Operator thêm thiết bị Router Gateway và nhấn 'Run Audit'. Hệ thống mở kết nối SSH chỉ đọc và phân tích cấu hình."
- **Hành động**:
  - Đăng nhập tài khoản `demo_operator`.
  - Chọn thiết bị `Router-Demo-01` và bấm **Run Audit**.
  - Màn hình hiển thị danh sách 8 quy tắc CIS: phát hiện `NET-008 (Insecure HTTP Server Enabled)` báo trạng thái `FAIL`.
  - Bấm vào chi tiết finding để xem bằng chứng `ip http server` đã được che giấu bí mật.

### Đoạn 3: Trợ Lý AI Giải Thích & Snapshot Diff (Phút 3:30 – 5:00)
- **Lời thoại**: "Để hỗ trợ quản trị viên hiểu rõ mức độ rủi ro, NetSentry tích hợp LLM cục bộ (Ollama). Xin nhấn mạnh: **AI trong NetSentry chỉ giải thích rủi ro, tuyệt đối không bao giờ được phép sinh lệnh cấu hình CLI**. Điều này nhằm triệt tiêu hoàn toàn nguy cơ tấn công Prompt Injection từ nội dung router."
- **Hành động**:
  - Bấm nút **Explain with AI**.
  - Đọc phần tóm tắt rủi ro và thứ tự ưu tiên do AI sinh ra.
  - Chuyển sang tab **Snapshots & Baselines** để xem mốc chuẩn cấu hình và phát hiện sai lệch (Drift).

### Đoạn 4: Đề Xuất & Phê Duyệt Bản Vá 4 Mắt (Phút 5:00 – 6:30)
- **Lời thoại**: "Tiếp theo là quy trình khắc phục an toàn. Operator bấm 'Propose Remediation' cho lỗi NET-008. Lệnh sinh ra tuân thủ mẫu tĩnh `no ip http server`. Tuy nhiên, Operator không thể tự áp dụng thay đổi."
- **Hành động**:
  - Operator bấm **Propose Plan** -> Trạng thái kế hoạch là `PROPOSED`.
  - Operator thử bấm Duyệt -> Hệ thống báo lỗi từ chối quyền (403 Forbidden).
  - Đăng xuất Operator; Đăng nhập `demo_admin`.
  - Admin duyệt kế hoạch -> Nhập lại mật khẩu (Step-up Authentication) để chống chiếm phiên -> Kế hoạch chuyển sang `APPROVED`.

### Đoạn 5: Áp Dụng Bản Vá, Xác Minh & Hoàn Tác (Phút 6:30 – 8:00)
- **Lời thoại**: "Admin tiến hành áp dụng bản vá (Apply Plan). Hệ thống thực hiện Dry-Run hoặc Live SSH ghi cấu hình, sau đó tự động kích hoạt một phiên kiểm toán độc lập (Verification Audit) để thẩm định kết quả."
- **Hành động**:
  - Admin bấm **Apply Plan** -> Xác nhận tên thiết bị `Router-Demo-01`.
  - Tiến trình nền thực thi: hiển thị các bước kết nối, gửi lệnh, kiểm tra lại.
  - Trạng thái kế hoạch cập nhật `VERIFIED` và lưu cấu hình (`write memory`).
  - Mở tab **Compare** để thấy `NET-008` đã chuyển từ `FAIL` sang `FIXED`.

### Đoạn 6: Trình Diễn Cơ Chế Chống Tấn Công (Phút 8:00 – 9:30)
- **Lời thoại**: "Để chứng minh độ tin cậy của thiết kế an toàn, chúng tôi thực hiện các kịch bản cố tình làm sai: Viewer cố sửa cấu hình bị chặn; Admin tự đề xuất và tự duyệt bị chặn; và router có banner chứa mã Prompt Injection độc hại vẫn bị bộ lọc của NetSentry vô hiệu hóa."
- **Hành động**:
  - Mở tab **Security Events** để cho thấy toàn bộ lịch sử thao tác được ghi vết chi tiết, không rò rỉ bất kỳ mật khẩu nào.

### Đoạn 7: Tổng Kết & Trả Lời Câu Hỏi (Phút 9:30 – 10:00)
- **Lời thoại**: "NetSentry đã đạt 100% các tiêu chí nghiệm thu bảo mật và độ chính xác kiểm toán. Cảm ơn thầy cô và các bạn đã lắng nghe."

---

## 3. Kịch Bản Dự Phòng Sự Cố (Fallback Plan)

- **Nếu Router Lab bị mất nguồn / mất kết nối mạng**:
  - Ngay lập tức chuyển sang chạy API dev server với mock device:
    ```bash
    .venv/bin/python scripts/run_api_with_fake_device.py --fixture insecure --port 8000
    ```
  - Trình duyệt thao tác mượt mà với dữ liệu giả lập giống hệt thiết bị thật, giải thích rõ với hội đồng đây là cơ chế kiểm thử tích hợp sẵn của dự án.
- **Nếu Ollama phản hồi chậm**:
  - Hệ thống tự động kích hoạt bộ nhớ đệm (cache) hoặc hiển thị kết quả phân tích mẫu đã lưu sẵn từ audit trước.
