"""Fixed, human-verified remediation templates and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.domain.entities.finding import Finding
from app.domain.entities.remediation import RiskLevel
from app.domain.errors import NotEligibleError
from app.remediation.command_policy import validate_commands


@dataclass(frozen=True, slots=True)
class RemediationTemplate:
    template_id: str
    version: int
    rule_id: str
    platforms: tuple[str, ...]
    risk_level: RiskLevel
    commands: tuple[str, ...]
    impact_vi: str
    risks_vi: tuple[str, ...]
    expected_verification: tuple[str, str]  # e.g. ("NET-008", "PASS")
    reversible: bool
    rollback_note_vi: str


@dataclass(frozen=True, slots=True)
class ManualGuidance:
    rule_id: str
    title: str
    reason_vi: str
    remediation_hint: str
    verification_hint: str


# Fixed verified templates for NET-008 and NET-004
TEMPLATE_NET_008_V1 = RemediationTemplate(
    template_id="NET-008-v1",
    version=1,
    rule_id="NET-008",
    platforms=("cisco_ios",),
    risk_level=RiskLevel.LOW,
    commands=("no ip http server",),
    impact_vi="Tắt dịch vụ máy chủ HTTP không mã hóa (cổng 80) trên thiết bị.",
    risks_vi=(
        "Nếu quản trị viên đang quản lý thiết bị qua giao diện web HTTP sẽ mất quyền truy cập web.",
        "Truy cập SSH và các giao thức quản trị từ xa khác không bị ảnh hưởng.",
        "Dịch vụ HTTPS an toàn (ip http secure-server) không bị đụng tới.",
    ),
    expected_verification=("NET-008", "PASS"),
    reversible=True,
    rollback_note_vi="Có thể hoàn tác bằng lệnh 'ip http server' trong chế độ cấu hình toàn cục.",
)

TEMPLATE_NET_004_V1 = RemediationTemplate(
    template_id="NET-004-v1",
    version=1,
    rule_id="NET-004",
    platforms=("cisco_ios",),
    risk_level=RiskLevel.LOW,
    commands=("service password-encryption",),
    impact_vi="Mã hóa dạng Type 7 cho toàn bộ mật khẩu văn bản thuần hiện có trong cấu hình.",
    risks_vi=(
        "Mã hóa Type 7 là thuật toán yếu, chỉ chống nhìn trộm màn hình (shoulder surfing), không thay thế được 'enable secret'.",
        "Nếu tắt lại bằng 'no service password-encryption' thì các mật khẩu đã mã hóa sẽ không được giải mã trở lại văn bản thuần.",
    ),
    expected_verification=("NET-004", "PASS"),
    reversible=False,
    rollback_note_vi="Không thể đảo ngược thực chất: tắt tính năng bằng 'no service password-encryption' không giải mã các mật khẩu đã lưu.",
)

_TEMPLATES_BY_RULE: dict[str, RemediationTemplate] = {
    "NET-008": TEMPLATE_NET_008_V1,
    "NET-004": TEMPLATE_NET_004_V1,
}
TEMPLATE_REGISTRY = _TEMPLATES_BY_RULE

# Rules that require manual intervention only (high risk of lockout or requires admin credentials/ACL choice)
_MANUAL_GUIDANCES: tuple[ManualGuidance, ...] = (
    ManualGuidance(
        rule_id="NET-001",
        title="VTY Transport Input",
        reason_vi="Thay đổi cấu hình VTY có thể dẫn đến nguy cơ tự khóa mình khỏi router nếu SSH chưa được kích hoạt đầy đủ.",
        remediation_hint="Cấu hình 'line vty 0 4' và đặt 'transport input ssh' sau khi xác nhận SSH hoạt động.",
        verification_hint="Kiểm tra 'show running-config | section line vty' đảm bảo không còn telnet.",
    ),
    ManualGuidance(
        rule_id="NET-002",
        title="SSH Version 2",
        reason_vi="Yêu cầu sinh khóa RSA (crypto key generate rsa) và đặt domain-name trước khi bật SSH v2.",
        remediation_hint="Cấu hình 'ip ssh version 2' sau khi đã tạo RSA key tối thiểu 2048 bits.",
        verification_hint="Kiểm tra 'show ip ssh' hiển thị SSH Version 2.0.",
    ),
    ManualGuidance(
        rule_id="NET-003",
        title="Enable Secret Password",
        reason_vi="Cần quản trị viên tự chọn và nhập mật khẩu bí mật mới với độ phức tạp cao.",
        remediation_hint="Cấu hình 'enable secret <strong-password>' trong global configuration.",
        verification_hint="Kiểm tra 'show running-config | include enable secret'.",
    ),
    ManualGuidance(
        rule_id="NET-005",
        title="SNMP Community String",
        reason_vi="Cần xác định chuỗi community riêng biệt và danh sách ACL kiểm soát truy cập NMS.",
        remediation_hint="Xóa community mặc định (public/private) và đặt community mới kèm ACL chỉ định IP NMS.",
        verification_hint="Kiểm tra 'show snmp community'.",
    ),
    ManualGuidance(
        rule_id="NET-006",
        title="VTY Access-Class Restriction",
        reason_vi="Yêu cầu xác định rõ dải địa chỉ IP của trạm quản trị trước khi gán ACL vào đường VTY.",
        remediation_hint="Tạo access-list cho phép dải IP quản trị và gán 'access-class <acl> in' trên line vty.",
        verification_hint="Kiểm tra 'show running-config | section line vty'.",
    ),
    ManualGuidance(
        rule_id="NET-007",
        title="Login Banner",
        reason_vi="Nội dung banner pháp lý cần được phòng pháp chế hoặc ban quản trị doanh nghiệp phê duyệt.",
        remediation_hint="Cấu hình 'banner motd ^<thông báo pháp lý>^' trong global configuration.",
        verification_hint="Kiểm tra 'show running-config | section banner'.",
    ),
)


def get_template(rule_id: str) -> RemediationTemplate:
    """Return template for the given rule_id, or raise NotEligibleError."""
    tmpl = _TEMPLATES_BY_RULE.get(rule_id)
    if tmpl is None:
        raise NotEligibleError(f"Rule {rule_id!r} is not eligible for automated remediation.")
    return tmpl


def get_all_templates() -> list[RemediationTemplate]:
    """Return list of all registered templates."""
    return list(_TEMPLATES_BY_RULE.values())


def get_manual_guidances() -> list[ManualGuidance]:
    """Return static manual guidance list for rules without automated templates."""
    return list(_MANUAL_GUIDANCES)


def build_plan_commands(template: RemediationTemplate, finding: Finding) -> tuple[str, ...]:
    """Extract commands strictly from template, without interpolating any finding content.

    Validates commands against command policy.
    """
    validate_commands(template.commands)
    # Strictly return template commands as a fixed immutable tuple
    return tuple(template.commands)
