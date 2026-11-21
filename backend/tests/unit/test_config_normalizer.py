from __future__ import annotations

from app.security.config_normalizer import ConfigNormalizer


def test_config_normalizer_removes_time_varying_lines():
    raw_config = (
        "\r\n\r\n"
        "Building configuration...\r\n"
        "Current configuration : 2450 bytes\r\n"
        "! Last configuration change at 12:00:00 UTC Sun Nov 15 2026\r\n"
        "! NVRAM config last updated at 12:01:00 UTC Sun Nov 15 2026\r\n"
        "! No configuration change since last restart\r\n"
        "version 15.2   \r\n"
        "hostname Lab-Router-01 \r\n"
        "ntp clock-period 171819\r\n"
        "Using 1200 out of 5000 bytes\r\n"
        "interface GigabitEthernet0/0\r\n"
        " ip address 10.0.0.1 255.255.255.0\r\n"
        "\r\n\r\n"
    )

    normalized = ConfigNormalizer.normalize(raw_config)

    # Line endings normalized
    assert "\r" not in normalized

    # Time varying lines removed
    assert "Building configuration..." not in normalized
    assert "Current configuration" not in normalized
    assert "Last configuration change at" not in normalized
    assert "NVRAM config last updated" not in normalized
    assert "No configuration change since last restart" not in normalized
    assert "ntp clock-period" not in normalized
    assert "Using 1200 out of 5000 bytes" not in normalized

    # Real lines preserved and stripped
    expected_lines = [
        "version 15.2",
        "hostname Lab-Router-01",
        "interface GigabitEthernet0/0",
        " ip address 10.0.0.1 255.255.255.0",
    ]
    assert normalized.split("\n") == expected_lines
