from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware

COOKIE = {"Cookie": "netsentry_session=x"}


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.post("/api/v1/x")
    def post_x() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/x")
    def get_x() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_same_origin_post_passes() -> None:
    r = _client().post("/api/v1/x", headers={**COOKIE, "Origin": "http://testserver"})
    assert r.status_code == 200


def test_null_origin_is_blocked() -> None:
    r = _client().post("/api/v1/x", headers={**COOKIE, "Origin": "null"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_lookalike_origin_suffix_is_blocked() -> None:
    r = _client().post("/api/v1/x", headers={**COOKIE, "Origin": "http://testserver.evil.com"})
    assert r.status_code == 403


def test_origin_match_is_case_insensitive() -> None:
    r = _client().post("/api/v1/x", headers={**COOKIE, "Origin": "http://TESTSERVER"})
    assert r.status_code == 200


def test_referer_fallback_when_origin_missing() -> None:
    r = _client().post("/api/v1/x", headers={**COOKIE, "Referer": "http://testserver/page"})
    assert r.status_code == 200


def test_missing_origin_and_referer_is_blocked() -> None:
    assert _client().post("/api/v1/x", headers=COOKIE).status_code == 403


def test_get_is_not_checked() -> None:
    assert _client().get("/api/v1/x", headers={**COOKIE, "Origin": "null"}).status_code == 200


def test_blocked_response_still_has_security_headers() -> None:
    r = _client().post("/api/v1/x", headers={**COOKIE, "Origin": "null"})
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Content-Security-Policy"].startswith("default-src 'self'")


def test_docs_page_has_no_csp_but_api_has() -> None:
    c = _client()
    assert "Content-Security-Policy" not in c.get("/docs").headers
    assert "Content-Security-Policy" in c.get("/api/v1/x").headers
