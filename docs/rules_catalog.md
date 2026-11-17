# NetSentry – Danh mục Rule Kiểm toán Cấu hình Cisco IOS (Rules Catalog)

Tài liệu này mô tả chi tiết 8 quy tắc kiểm toán cấu hình Cisco IOS (`AuditRule`) được tích hợp trong NetSentry Rule Engine (`app/rules/`).

---

## 1. Bảng tổng quan 8 Rule

| Rule ID | Class Name | File | Severity | Platforms | PASS | FAIL | UNKNOWN |
|---|---|---|---|---|---|---|---|
| **NET-001** | `TelnetRule` | `telnet_rule.py` | HIGH | `cisco_ios` | Mọi block VTY đều có `transport input` và không chứa `telnet`/`all` | Có block VTY cho phép `telnet` hoặc `all` | Không có block VTY hoặc block VTY thiếu `transport input` |
| **NET-002** | `SshVersionRule` | `ssh_rule.py` | MEDIUM | `cisco_ios` | Có `ip ssh version 2` | Có `ip ssh version 1` hoặc thiếu `ip ssh version 2` | *(Không có)* |
| **NET-003** | `PlainTextCredentialRule` | `password_rule.py` | HIGH | `cisco_ios` | Chỉ dùng `secret` (`enable secret`, `username ... secret`), không có plaintext password | Có `enable password`, `username ... password`, hoặc `password` trong block `line` | *(Không có)* |
| **NET-004** | `PasswordEncryptionServiceRule` | `password_rule.py` | LOW | `cisco_ios` | Có `service password-encryption` | Thiếu `service password-encryption` hoặc có `no service password-encryption` | *(Không có)* |
| **NET-005** | `VtyExecTimeoutRule` | `vty_timeout_rule.py` | MEDIUM | `cisco_ios` | Mọi block VTY có `exec-timeout` hợp lệ $\le$ 600 giây (10 phút) | `exec-timeout 0 0` (tắt timeout) hoặc tổng thời gian > 600s | Không có block VTY hoặc block VTY thiếu dòng `exec-timeout` |
| **NET-006** | `VtyAccessClassRule` | `vty_acl_rule.py` | MEDIUM | `cisco_ios` | Mọi block VTY đều áp dụng `access-class <ACL> in` | Có block VTY thiếu cấu hình `access-class ... in` | Không có block VTY |
| **NET-007** | `SnmpCommunityRule` | `snmp_rule.py` | MEDIUM / HIGH | `cisco_ios` | Không cấu hình SNMP community strings | Tồn tại dòng `snmp-server community` (nâng lên HIGH nếu quyền RW hoặc tên mặc định `public`/`private`) | *(Không có)* |
| **NET-008** | `HttpServerRule` | `http_server_rule.py` | MEDIUM | `cisco_ios` | Không bật HTTP không mã hóa hoặc có `no ip http server` | Có dòng `ip http server` | *(Không có)* |

> [!NOTE]
> **Độ ưu tiên đánh giá khi có nhiều block VTY (NET-001, NET-005, NET-006):**
> Tuân thủ nghiêm ngặt quy tắc **`FAIL > UNKNOWN > PASS`**. Nếu bất kỳ block VTY nào vi phạm, kết quả chung sẽ là `FAIL` ngay cả khi các block khác thiếu cấu hình hoặc đạt chuẩn.

---

## 2. Chi tiết từng Rule

### NET-001: Disallow Telnet on VTY lines
- **Class**: `app.rules.telnet_rule.TelnetRule`
- **Severity**: `HIGH`
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Ngăn chặn việc truyền tải thông tin quản trị và thông tin đăng nhập ở dạng văn bản thuần (plaintext) qua giao thức Telnet trên các phiên truy cập ảo (VTY).
- **Điều kiện đánh giá**:
  - `FAIL`: Tồn tại ít nhất một khối `line vty` có dòng `transport input` chứa tham số `telnet` hoặc `all`.
  - `PASS`: Tất cả các khối `line vty` đều có dòng `transport input` và chỉ chấp nhận các giao thức an toàn (vd: `ssh`, hoặc `none`).
  - `UNKNOWN`: Cấu hình không có khối `line vty` nào, hoặc có khối VTY nhưng thiếu dòng `transport input` (hành vi mặc định phụ thuộc vào phiên bản Cisco IOS).
- **Ví dụ Evidence**:
  - FAIL: `line vty 0 4: transport input telnet ssh`
  - PASS: `line vty 0 4: transport input ssh`
- **Remediation**: `Restrict VTY lines to SSH: under "line vty" blocks configure "transport input ssh".`
- **Verification**: `Run "show running-config | section line vty" and confirm transport input contains only secure protocols (e.g., ssh).`

---

### NET-002: Enforce SSH version 2
- **Class**: `app.rules.ssh_rule.SshVersionRule`
- **Severity**: `MEDIUM`
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Đảm bảo thiết bị áp dụng giao thức SSHv2 với các thuật toán mật mã an toàn, loại bỏ hoàn toàn các lỗ hổng của SSHv1.
- **Điều kiện đánh giá**:
  - `FAIL`: Có dòng `ip ssh version 1` hoặc hoàn toàn không có cấu hình `ip ssh version 2`.
  - `PASS`: Có cấu hình `ip ssh version 2`.
  - `UNKNOWN`: Không áp dụng (rule chỉ trả về PASS hoặc FAIL).
- **Ví dụ Evidence**:
  - FAIL: `ip ssh version 1` (hoặc rỗng nếu thiếu cấu hình)
  - PASS: `ip ssh version 2`
- **Remediation**: `Configure 'ip ssh version 2' in global configuration mode.`
- **Verification**: `Run "show ip ssh" and verify SSH version 2 is enabled.`

---

### NET-003: Disallow plaintext or weakly encrypted passwords
- **Class**: `app.rules.password_rule.PlainTextCredentialRule`
- **Severity**: `HIGH`
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Ngăn ngừa việc lưu trữ mật khẩu dưới dạng văn bản rõ (type 0) hoặc mã hóa yếu dễ giải mã ngược (type 7 của Cisco) trong file cấu hình.
- **Điều kiện đánh giá**:
  - `FAIL`: Tồn tại bất kỳ dòng nào sau đây:
    - Cấp toàn cục: `enable password ...`
    - Cấp toàn cục: `username <name> ... password ...`
    - Cấp khối đường truyền (`line con`, `line aux`, `line vty`): `password ...`
  - `PASS`: Thiết bị chỉ sử dụng hàm băm một chiều an toàn (`enable secret`, `username ... secret`) và không có mật khẩu dạng `password`.
  - `UNKNOWN`: Không áp dụng.
- **Ví dụ Evidence (Đã che bí mật)**:
  - FAIL: `enable password 0 <REDACTED>`
  - FAIL: `username admin privilege 15 password 0 <REDACTED>`
  - FAIL: `line con 0: password 7 <REDACTED>`
- **Remediation**: `Replace 'enable password' with 'enable secret', and use 'username ... secret' instead of 'password'. Remove plaintext line passwords.`
- **Verification**: `Run "show running-config | include (password|secret)" and confirm only secure hashes ('secret') are used.`

---

### NET-004: Enable Cisco password encryption service
- **Class**: `app.rules.password_rule.PasswordEncryptionServiceRule`
- **Severity**: `LOW`
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Bật tính năng xáo trộn mật khẩu tự động trong file cấu hình nhằm chống lại việc nhìn trộm màn hình (shoulder surfing).
- **Điều kiện đánh giá**:
  - `FAIL`: Thiếu lệnh `service password-encryption` hoặc cấu hình chứa `no service password-encryption`.
  - `PASS`: Có lệnh `service password-encryption`.
  - `UNKNOWN`: Không áp dụng.
- **Ví dụ Evidence**:
  - FAIL: `no service password-encryption`
  - PASS: `service password-encryption`
- **Remediation**: `Configure 'service password-encryption' in global configuration mode.`
- **Verification**: `Run "show running-config | include service password-encryption" and verify the service is active.`

---

### NET-005: Enforce VTY executive session timeout
- **Class**: `app.rules.vty_timeout_rule.VtyExecTimeoutRule`
- **Severity**: `MEDIUM`
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Tự động ngắt các phiên quản trị VTY khi không có tương tác, giảm thiểu rủi ro bị chiếm quyền điều khiển phiên bỏ quên.
- **Điều kiện đánh giá**:
  - `FAIL`: Có block VTY cấu hình `exec-timeout 0 0` (tắt cơ chế timeout) hoặc cấu hình thời gian chờ vượt quá ngưỡng an toàn 600 giây (10 phút).
  - `PASS`: Tất cả các block VTY đều cấu hình `exec-timeout` hợp lệ $\le 600$ giây.
  - `UNKNOWN`: Cấu hình không có block VTY nào hoặc có block VTY nhưng thiếu dòng `exec-timeout`.
- **Ví dụ Evidence**:
  - FAIL: `line vty 0 4: exec-timeout 0 0 (timeout disabled)`
  - FAIL: `line vty 0 4: exec-timeout 15 0 (900s > 600s)`
  - PASS: `line vty 0 4: exec-timeout 5 0`
- **Remediation**: `Configure "exec-timeout 10 0" or less (max 600s) under all "line vty" blocks.`
- **Verification**: `Run "show running-config | section line vty" and verify exec-timeout is <= 600 seconds.`

---

### NET-006: Restrict VTY access using Access Control List
- **Class**: `app.rules.vty_acl_rule.VtyAccessClassRule`
- **Severity**: `MEDIUM`
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Giới hạn dải địa chỉ IP nguồn được phép mở phiên kết nối quản trị VTY vào thiết bị.
- **Điều kiện đánh giá**:
  - `FAIL`: Có ít nhất một block VTY thiếu cấu hình `access-class <ACL> in`.
  - `PASS`: Tất cả các block VTY đều có cấu hình `access-class ... in`.
  - `UNKNOWN`: Cấu hình không có khối VTY nào.
- **Ví dụ Evidence**:
  - FAIL: `line vty 0 4: missing 'access-class ... in'`
  - PASS: `line vty 0 4: access-class 10 in`
- **Remediation**: `Configure "access-class <ACL_NAME_OR_NUMBER> in" under all "line vty" blocks.`
- **Verification**: `Run "show running-config | section line vty" and verify access-class is applied in the inbound direction.`

---

### NET-007: Disallow insecure SNMP community strings
- **Class**: `app.rules.snmp_rule.SnmpCommunityRule`
- **Severity**: `MEDIUM` (Tự động nâng lên `HIGH` nếu quyền là `RW` hoặc chuỗi tên là mặc định `public`/`private`)
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Loại bỏ các chuỗi SNMP community (giao thức v1/v2c truyền mật khẩu rõ), đặc biệt là các quyền ghi (RW) cho phép thay đổi cấu hình thiết bị trái phép.
- **Điều kiện đánh giá**:
  - `FAIL`: Tồn tại bất kỳ dòng cấu hình `snmp-server community ...` nào.
  - `PASS`: Không cấu hình SNMP community strings.
  - `UNKNOWN`: Không áp dụng.
- **Ví dụ Evidence (Đã che bí mật)**:
  - FAIL (HIGH): `snmp-server community <REDACTED> RW 10`
  - FAIL (HIGH): `snmp-server community <REDACTED> RO` (khi tên là public/private)
  - FAIL (MEDIUM): `snmp-server community <REDACTED> RO`
- **Remediation**: `Remove community strings using 'no snmp-server community <string>' and migrate to SNMPv3 with SHA authentication and AES encryption.`
- **Verification**: `Run "show running-config | include snmp-server community" and verify no community strings are active.`

---

### NET-008: Disable unencrypted HTTP server
- **Class**: `app.rules.http_server_rule.HttpServerRule`
- **Severity**: `MEDIUM`
- **Platforms**: `("cisco_ios",)`
- **Mục đích**: Tắt dịch vụ giao diện web không mã hóa (HTTP cổng 80) của Cisco IOS nhằm tránh lộ thông tin và thông tin đăng nhập trên đường truyền.
- **Điều kiện đánh giá**:
  - `FAIL`: Tồn tại dòng `ip http server`.
  - `PASS`: Cấu hình có lệnh tường minh `no ip http server` hoặc hoàn toàn không chứa dòng `ip http server` (Lưu ý: lệnh `ip http secure-server` dành cho HTTPS an toàn và không bị coi là vi phạm).
  - `UNKNOWN`: Không áp dụng.
- **Ví dụ Evidence**:
  - FAIL: `ip http server`
  - PASS: `no ip http server`
- **Remediation**: `Disable unencrypted HTTP server using 'no ip http server'. Use 'ip http secure-server' (HTTPS) if web management is required.`
- **Verification**: `Run "show running-config | include ip http server" and verify unencrypted HTTP server is disabled or absent.`
