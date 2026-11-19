"""Tests for SPA static file serving and path traversal prevention (Section 9.11)."""

from pathlib import Path
from starlette.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.database import init_db


def test_spa_static_serving(tmp_path: Path) -> None:
    db_file = tmp_path / "spa.db"
    init_db(db_file)

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    index_file = dist_dir / "index.html"
    index_file.write_text("<!doctype html><html><body>NetSentry SPA</body></html>", encoding="utf-8")

    asset_dir = dist_dir / "assets"
    asset_dir.mkdir()
    css_file = asset_dir / "style.css"
    css_file.write_text("body { color: red; }", encoding="utf-8")

    settings = Settings(
        db_path=db_file,
        api_key="a" * 32,
        auth_disabled=True,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=False,
        public_mode=False,
        serve_frontend=True,
        frontend_dist=dist_dir,
    )

    app = create_app(settings=settings)
    client = TestClient(app)

    # 1. Root / returns index.html
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert "NetSentry SPA" in root_res.text

    # 2. Asset file /assets/style.css returns file content
    asset_res = client.get("/assets/style.css")
    assert asset_res.status_code == 200
    assert "body { color: red; }" in asset_res.text

    # 3. Client SPA route /devices/abc returns index.html (SPA fallback)
    spa_res = client.get("/devices/abc")
    assert spa_res.status_code == 200
    assert "NetSentry SPA" in spa_res.text

    # 4. Unknown /api/v1/nonexistent route returns 404 JSON, NOT index.html
    api_res = client.get("/api/v1/nonexistent")
    assert api_res.status_code == 404
    assert api_res.json()["error"]["code"] == "NOT_FOUND"

    # 5. Path traversal attempt fails
    trav_res = client.get("/..%2f..%2fetc/passwd")
    assert trav_res.status_code in (404, 400)
