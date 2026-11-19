"""Unit tests for rate limiter and client IP resolution (Section 9.5)."""

from app.security.client_ip import resolve_client_ip
from app.security.rate_limiter import InMemorySlidingWindowLimiter


class TestClientIpResolution:
    def test_fallback_to_peer_host_when_no_trusted_header_configured(self) -> None:
        ip = resolve_client_ip(
            peer_host="203.0.113.5",
            header_value="198.51.100.10",
            trusted_header_configured="",
        )
        assert ip == "203.0.113.5"

    def test_trusts_header_when_peer_is_loopback_ipv4(self) -> None:
        ip = resolve_client_ip(
            peer_host="127.0.0.1",
            header_value="203.0.113.42",
            trusted_header_configured="CF-Connecting-IP",
        )
        assert ip == "203.0.113.42"

    def test_trusts_header_when_peer_is_loopback_ipv6(self) -> None:
        ip = resolve_client_ip(
            peer_host="::1",
            header_value="203.0.113.42",
            trusted_header_configured="CF-Connecting-IP",
        )
        assert ip == "203.0.113.42"

    def test_ignores_header_when_peer_is_not_loopback_anti_spoofing(self) -> None:
        # Non-loopback peer attempts to spoof CF-Connecting-IP header
        ip = resolve_client_ip(
            peer_host="192.168.1.100",
            header_value="10.0.0.1",
            trusted_header_configured="CF-Connecting-IP",
        )
        assert ip == "192.168.1.100"

    def test_extracts_first_ip_from_comma_separated_header(self) -> None:
        ip = resolve_client_ip(
            peer_host="127.0.0.1",
            header_value="203.0.113.1, 10.0.0.1, 192.168.1.1",
            trusted_header_configured="X-Forwarded-For",
        )
        assert ip == "203.0.113.1"

    def test_invalid_header_ip_format_falls_back_to_peer_host(self) -> None:
        ip = resolve_client_ip(
            peer_host="127.0.0.1",
            header_value="invalid-ip-string; injection",
            trusted_header_configured="CF-Connecting-IP",
        )
        assert ip == "127.0.0.1"


class TestInMemorySlidingWindowLimiter:
    def test_sliding_window_allows_up_to_max_requests(self) -> None:
        limiter = InMemorySlidingWindowLimiter(max_requests=3, window_seconds=10)
        t0 = 1000.0

        # Request 1, 2, 3 should be allowed
        allowed, retry = limiter.is_allowed("user-ip-1", now=t0)
        assert allowed is True
        assert retry == 0

        allowed, retry = limiter.is_allowed("user-ip-1", now=t0 + 1)
        assert allowed is True
        assert retry == 0

        allowed, retry = limiter.is_allowed("user-ip-1", now=t0 + 2)
        assert allowed is True
        assert retry == 0

        # Request 4 in same window must be blocked
        allowed, retry = limiter.is_allowed("user-ip-1", now=t0 + 3)
        assert allowed is False
        assert retry == 7  # oldest was t0 (1000.0) + 10s window - now (1003.0) = 7s

    def test_sliding_window_slides_and_allows_after_cutoff(self) -> None:
        limiter = InMemorySlidingWindowLimiter(max_requests=2, window_seconds=10)
        t0 = 1000.0

        assert limiter.is_allowed("user-ip-2", now=t0)[0] is True
        assert limiter.is_allowed("user-ip-2", now=t0 + 2)[0] is True
        assert limiter.is_allowed("user-ip-2", now=t0 + 4)[0] is False

        # At t0 + 10.1s, the first request at t0 has expired
        allowed, retry = limiter.is_allowed("user-ip-2", now=t0 + 10.1)
        assert allowed is True
        assert retry == 0

    def test_different_keys_are_isolated(self) -> None:
        limiter = InMemorySlidingWindowLimiter(max_requests=1, window_seconds=10)
        t0 = 1000.0

        assert limiter.is_allowed("ip-A", now=t0)[0] is True
        assert limiter.is_allowed("ip-A", now=t0)[0] is False

        # ip-B is independent
        assert limiter.is_allowed("ip-B", now=t0)[0] is True

    def test_reset(self) -> None:
        limiter = InMemorySlidingWindowLimiter(max_requests=1, window_seconds=10)
        limiter.is_allowed("ip-X", now=100.0)
        assert limiter.is_allowed("ip-X", now=101.0)[0] is False

        limiter.reset("ip-X")
        assert limiter.is_allowed("ip-X", now=102.0)[0] is True
