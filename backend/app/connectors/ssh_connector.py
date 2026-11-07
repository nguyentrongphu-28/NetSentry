import os
import paramiko
from netmiko import ConnectHandler


def collect_device_info(
    host: str,
    username: str,
    password: str,
) -> dict:
    ssh_config_file = "/root/.ssh/config"

    # Nạp cấu hình SSH từ file nếu tồn tại
    if os.path.exists(ssh_config_file):
        ssh_config = paramiko.SSHConfig()
        with open(ssh_config_file) as f:
            ssh_config.parse(f)

    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": username,
        "password": password,
        "port": 22,
        "conn_timeout": 15,
        "banner_timeout": 15,
        "auth_timeout": 15,
        "ssh_config_file": ssh_config_file,
        "use_keys": False,
        "allow_agent": False,
    }

    with ConnectHandler(**device) as connection:
        prompt = connection.find_prompt()
        hostname = prompt.rstrip("#>").strip()

        version_output = connection.send_command(
            "show version",
            read_timeout=30,
        )

        interface_output = connection.send_command(
            "show ip interface brief",
            read_timeout=30,
        )

        return {
            "hostname": hostname,
            "ip_address": host,
            "device_type": "cisco_ios",
            "version_output": version_output,
            "interface_output": interface_output,
        }
