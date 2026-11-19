"""Unit tests for config public mode invariants and security middleware (Sections 9.8 & 9.9)."""

from pathlib import Path
import pytest
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from app.api.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware
from app.core.config import Settings


class TestPublicModeConfigInvariants:
    def test_public_mode_disallows_auth_disabled(self) -> None:
        env = {
            "NETSENTRY_PUBLIC_MODE": "1",
            "NETSENTRY_AUTH_DISABLED": "1",
            "NETSENTRY_ALLOWED_NETWORKS": "192.168.1.0/24",
        }
        with pytest.raises(RuntimeError, match="NETSENTRY_AUTH_DISABLED=1 is strictly forbidden"):
            Settings.from_env(env)

    def test_public_mode_disallows_empty_allowed_networks(self) -> None:
        env = {
            "NETSENTRY_PUBLIC_MODE": "1",
            "NETSENTRY_AUTH_DISABLED": "0",
            "NETSENTRY_ALLOWED_NETWORKS": "",
        }
        with pytest.raises(RuntimeError, match="NETSENTRY_ALLOWED_NETWORKS cannot be empty in public mode"):
            Settings.from_env(env)

    def test_public_mode_forces_invariants(self) -> None:
        env = {
            "NETSENTRY_PUBLIC_MODE": "1",
            "NETSENTRY_AUTH_DISABLED": "0",
            "NETSENTRY_ALLOWED_NETWORKS": "10.0.0.0/8",
            "NETSENTRY_ENABLE_DOCS": "1",  # should be overridden to False
            "NETSENTRY_SESSION_COOKIE_SECURE": "0",  # should be overridden to True
            "NETSENTRY_ALLOW_BODY_CREDENTIALS": "1",  # should be overridden to False
            "NETSENTRY_API_KEY_AUTH": "1",  # should be overridden to False
        }
        cfg = Settings.from_env(env)
        assert cfg.public_mode is True
        assert cfg.enable_docs is False
        assert cfg.session_cookie_secure is True
        assert cfg.allow_body_credentials is False
        assert cfg.api_key_auth is False


from starlette.routing import Route


class TestSecurityMiddleware:
    def _create_app(self, cors_origins: tuple[str, ...] = (), allowed_hosts: list[str] | None = None):
        async def api_endpoint(request):
            return JSONResponse({"ok": True})

        async def health_endpoint(request):
            return Response("ok", media_type="text/plain")

        routes = [
            Route("/api/test", api_endpoint, methods=["GET", "POST"]),
            Route("/health", health_endpoint, methods=["GET"]),
        ]

        app = Starlette(routes=routes)
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(OriginCheckMiddleware, cors_origins=cors_origins)
        if allowed_hosts:
            app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

        return app

    def test_security_headers_and_no_store(self) -> None:
        app = self._create_app()
        client = TestClient(app)

        res = client.get("/api/test")
        assert res.status_code == 200
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert res.headers["Referrer-Policy"] == "no-referrer"
        assert "Content-Security-Policy" in res.headers
        assert "no-store" in res.headers["Cache-Control"]

        # /health does not have no-store
        health_res = client.get("/health")
        assert health_res.status_code == 200
        assert "Cache-Control" not in health_res.headers

    def test_origin_check_blocks_missing_origin_when_session_cookie_present(self) -> None:
        app = self._create_app()
        client = TestClient(app)

        # POST with session cookie but missing Origin/Referer -> 403
        client.cookies.set("netsentry_session", "fake_session_token")
        res = client.post("/api/test")
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"

    def test_origin_check_allows_matching_origin_and_host(self) -> None:
        app = self._create_app()
        client = TestClient(app)

        client.cookies.set("netsentry_session", "fake_session_token")
        res = client.post(
            "/api/test",
            headers={"Host": "app.example.com", "Origin": "http://app.example.com"},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_origin_check_blocks_mismatched_origin(self) -> None:
        app = self._create_app()
        client = TestClient(app)

        client.cookies.set("netsentry_session", "fake_session_token")
        res = client.post(
            "/api/test",
            headers={"Host": "app.example.com", "Origin": "http://evil-attacker.com"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"

    def test_trusted_host_blocks_unauthorized_host(self) -> None:
        app = self._create_app(allowed_hosts=["localhost", "127.0.0.1", "*.trycloudflare.com"])
        client = TestClient(app)

        # Allowed host
        res_ok = client.get("/health", headers={"Host": "random123.trycloudflare.com"})
        assert res_ok.status_code == 200

        # Disallowed host -> 400
        res_bad = client.get("/health", headers={"Host": "attacker.com"})
        assert res_bad.status_code == 400
