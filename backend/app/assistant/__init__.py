"""NetSentry AI — Tuần 7: AI assistant (giải thích finding + đề xuất có cấu trúc).

Nguyên tắc cứng (được test tự động):
  * Module này KHÔNG import netmiko/paramiko/socket/subprocess -> AI không có đường SSH tới thiết bị.
  * Mọi đầu ra của LLM là DỮ LIỆU không tin cậy: phải qua validator trước khi tới người dùng.
  * LLM chỉ được đề xuất tham số cho đúng 1 action trong allowlist; việc thực thi vẫn do luồng
    Preview -> Validate -> Approve -> Execute -> Verify của backend (module của A/B) đảm nhiệm.
"""
from .service import AssistantService
from .policy_gate import PolicyGate, load_policy
from .llm_client import LLMClient, MockLLM, make_client_from_env

__all__ = ["AssistantService", "PolicyGate", "load_policy", "LLMClient", "MockLLM", "make_client_from_env"]
