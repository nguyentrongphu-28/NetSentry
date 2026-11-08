# scripts/fakes.py
"""Thiết bị Cisco giả dùng cho test (không cần phần cứng). Output mô phỏng theo định dạng IOS 15.x."""


class NetmikoTimeoutException(Exception):
    pass


class NetmikoAuthenticationException(Exception):
    pass


SHOW_VERSION = """Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 15.0(2)SE11, RELEASE SOFTWARE (fc3)
Switch-LAB uptime is 3 weeks, 2 days, 4 hours, 12 minutes
cisco WS-C2960-24TT-L (PowerPC405) processor (revision B0) with 65536K bytes of memory.
Processor board ID FOC1234X0AB
Model number                    : WS-C2960-24TT-L
System serial number            : FOC1234X0AB
"""

# Cấu hình THÔ có bí mật giả: dùng để chứng minh bản lưu ra đĩa đã được làm sạch
RAW_CONFIG = """Building configuration...

Current configuration : 1500 bytes
!
version 15.0
service password-encryption
hostname Switch-LAB
!
enable secret 5 $1$mK1q$FAKEHASHENABLE
username admin privilege 15 secret 5 $1$abc$FAKEHASHUSER
ip ssh version 2
snmp-server community S3cretCommunity RO
snmp-server community public RO
!
line vty 0 4
 password 7 060506324F41
 login
 transport input ssh
!
end
"""

VLAN_BRIEF_BEFORE = """
VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    Fa0/2, Fa0/3, Fa0/4, Fa0/5
                                                Fa0/6, Gi0/1, Gi0/2
1002 fddi-default                     act/unsup
1003 token-ring-default               act/unsup
1004 fddinet-default                  act/unsup
1005 trnet-default                    act/unsup
"""

VLAN_BRIEF_AFTER = """
VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    Fa0/2, Fa0/3, Fa0/4, Fa0/5
                                                Fa0/6, Gi0/2
20   IT_DEPT                          active    Gi0/1
1002 fddi-default                     act/unsup
1003 token-ring-default               act/unsup
1004 fddinet-default                  act/unsup
1005 trnet-default                    act/unsup
"""

SWITCHPORT_BEFORE = """Name: Gi0/1
Switchport: Enabled
Administrative Mode: dynamic auto
Operational Mode: static access
Administrative Trunking Encapsulation: dot1q
Access Mode VLAN: 1 (default)
Trunking Native Mode VLAN: 1 (default)
"""

SWITCHPORT_AFTER = """Name: Gi0/1
Switchport: Enabled
Administrative Mode: static access
Operational Mode: static access
Administrative Trunking Encapsulation: dot1q
Operational Trunking Encapsulation: native
Negotiation of Trunking: Off
Access Mode VLAN: 20 (IT_DEPT)
Trunking Native Mode VLAN: 1 (default)
"""

IF_RUNNING_BEFORE = """Building configuration...

Current configuration : 38 bytes
!
interface GigabitEthernet0/1
 switchport mode dynamic auto
 description lab-port
end
"""


class FakeConnection:
    def __init__(self, outputs, on_config=None, config_output=""):
        self.outputs = dict(outputs)
        self.on_config = on_config or {}
        self.config_output = config_output
        self.sent_config = []
        self.saved = False
        self.disconnected = False

    def check_enable_mode(self):
        return True

    def enable(self):
        pass

    def find_prompt(self):
        return "Switch-LAB#"

    def send_command(self, cmd, read_timeout=None):
        if cmd not in self.outputs:
            return f"% Invalid input detected at '^' marker.\n(fake: chưa khai báo output cho {cmd!r})"
        return self.outputs[cmd]

    def send_config_set(self, cmds, read_timeout=None):
        self.sent_config.append(list(cmds))
        self.outputs.update(self.on_config)
        return self.config_output

    def save_config(self):
        self.saved = True
        return "[OK]"

    def disconnect(self):
        self.disconnected = True


def make_factory(outputs=None, exc=None, **conn_kwargs):
    """Tạo connection_factory cho NetworkAdapter. exc: exception sẽ được raise khi kết nối."""
    holder = {"conn": None, "params": None}

    def factory(params):
        holder["params"] = params
        if exc is not None:
            raise exc
        holder["conn"] = FakeConnection(outputs or {}, **conn_kwargs)
        return holder["conn"]

    factory.holder = holder
    return factory


def standard_outputs():
    return {
        "show version": SHOW_VERSION,
        "show running-config": RAW_CONFIG,
        "show vlan brief": VLAN_BRIEF_BEFORE,
        "show interfaces GigabitEthernet0/1 switchport": SWITCHPORT_BEFORE,
        "show running-config interface GigabitEthernet0/1": IF_RUNNING_BEFORE,
    }
