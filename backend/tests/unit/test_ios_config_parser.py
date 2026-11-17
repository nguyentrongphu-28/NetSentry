from __future__ import annotations

from pathlib import Path
import textwrap
import pytest

from app.rules.ios_config_parser import IosConfigParser

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "configs"


@pytest.fixture
def parser() -> IosConfigParser:
    return IosConfigParser()


def test_empty_and_whitespace_input(parser: IosConfigParser):
    res_empty = parser.parse("")
    assert res_empty.global_lines == ()
    assert res_empty.blocks == ()

    res_ws = parser.parse("   \n\t\n  ")
    assert res_ws.global_lines == ()
    assert res_ws.blocks == ()


def test_comment_and_metadata_filtering(parser: IosConfigParser):
    raw = textwrap.dedent(
        """\
        !
        Building configuration...
        Current configuration : 1234 bytes
        Using 1234 out of 56789 bytes
        hostname Core-Router
        ! A comment line
        end
        """
    )
    parsed = parser.parse(raw)
    assert parsed.global_lines == ("hostname Core-Router",)
    assert parsed.blocks == ()


def test_blocks_and_children_parsing(parser: IosConfigParser):
    raw = textwrap.dedent(
        """\
        hostname R1
        interface GigabitEthernet0/0
         description LAN Port
         ip address 192.168.1.1 255.255.255.0
         no shutdown
        line vty 0 4
         transport input ssh
         exec-timeout 5 0
        ip ssh version 2
        """
    )
    parsed = parser.parse(raw)
    assert parsed.global_lines == ("hostname R1", "ip ssh version 2")
    assert len(parsed.blocks) == 2

    intf_block = parsed.blocks_starting_with("interface")[0]
    assert intf_block.header == "interface GigabitEthernet0/0"
    assert intf_block.children == (
        "description LAN Port",
        "ip address 192.168.1.1 255.255.255.0",
        "no shutdown",
    )

    vty_block = parsed.blocks_starting_with("line vty")[0]
    assert vty_block.header == "line vty 0 4"
    assert vty_block.children == ("transport input ssh", "exec-timeout 5 0")


def test_banner_multiline_and_single_line(parser: IosConfigParser):
    raw = textwrap.dedent(
        """\
        hostname Trap-Host
        banner motd ^C
        ======================================
        WARNING: transport input telnet is bad
        password 7 0822455D0A16
        ======================================
        ^C
        banner login # Single line banner #
        line vty 0 4
         transport input ssh
        """
    )
    parsed = parser.parse(raw)
    # The banner lines must be completely discarded
    assert parsed.global_lines == ("hostname Trap-Host",)
    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].header == "line vty 0 4"
    assert parsed.blocks[0].children == ("transport input ssh",)


def test_crlf_normalization(parser: IosConfigParser):
    raw = "hostname R1\r\nline vty 0 4\r\n transport input ssh\r\n"
    parsed = parser.parse(raw)
    assert parsed.global_lines == ("hostname R1",)
    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].children == ("transport input ssh",)


def test_fixtures_parsing(parser: IosConfigParser):
    for filename in ("ios_secure.cfg", "ios_insecure.cfg", "ios_minimal.cfg", "ios_banner_trap.cfg"):
        fixture_path = FIXTURES_DIR / filename
        assert fixture_path.exists(), f"Fixture {filename} missing"
        content = fixture_path.read_text(encoding="utf-8")
        parsed = parser.parse(content)
        assert parsed is not None
        assert isinstance(parsed.global_lines, tuple)
        assert isinstance(parsed.blocks, tuple)
