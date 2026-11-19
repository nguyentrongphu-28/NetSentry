"""Security middleware for NetSentry: security headers, Origin check, CSRF defense."""

from __future__ import annotations

from urllib.parse import urlparse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces standard HTTP security headers and no-store caching for API."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # 1. Standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # CSP header
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

        # 2. No-store cache for /api/ routes
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Enforces Origin/Host match on state-changing requests (CSRF mitigation)."""

    def __init__(self, app, cors_origins: tuple[str, ...] = ()) -> None:
        super().__init__(app)
        self.cors_origins = cors_origins

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check Origin for state-changing HTTP methods or /auth/login
        is_state_changing = request.method in ("POST", "PUT", "PATCH", "DELETE")
        has_session_cookie = "netsentry_session" in request.cookies
        is_login_endpoint = request.url.path.endswith("/auth/login")

        # Origin check applies when session cookie is present on mutation OR on login endpoint
        if is_state_changing and (has_session_cookie or is_login_endpoint):
            origin_header = request.headers.get("origin")
            referer_header = request.headers.get("referer")

            source_url = origin_header or referer_header
            if not source_url:
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "ORIGIN_NOT_ALLOWED", "message": "Missing Origin or Referer header"}},
                )

            parsed_source = urlparse(source_url)
            source_netloc = parsed_source.netloc.lower()

            # Compare with request Host header or configured CORS origins
            host_header = request.headers.get("host", "").lower()

            matches_host = source_netloc == host_header

            # Also allow if configured in CORS origins
            matches_cors = False
            for allowed in self.cors_origins:
                parsed_allowed = urlparse(allowed)
                if parsed_allowed.netloc.lower() == source_netloc:
                    matches_cors = True
                    break

            if not (matches_host or matches_cors):
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "ORIGIN_NOT_ALLOWED", "message": "Origin does not match request Host"}},
                )

        return await call_next(request)
