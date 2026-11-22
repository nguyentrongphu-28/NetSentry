"""SPA static file serving and fallback handler for NetSentry."""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that serves index.html for non-file SPA routes."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            index_path = Path(self.directory) / "index.html"
            if index_path.exists() and index_path.is_file():
                return FileResponse(index_path)
        return response


def mount_static_spa(app: FastAPI, dist_dir: Path | None) -> None:
    """Mount frontend/dist with SPA fallback if configured and exists."""
    if not dist_dir or not dist_dir.exists():
        return

    index_html = dist_dir / "index.html"
    if not index_html.exists():
        return

    # Mount static assets directory if it exists
    assets_dir = dist_dir / "assets"
    if assets_dir.exists() and assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # Do not catch /api/, /health or disabled docs routes (they must return 404 JSON, not SPA index.html)
        normalized_path = full_path.strip("/")
        if (
            full_path.startswith("api/")
            or full_path == "api"
            or full_path == "health"
            or normalized_path in ("docs", "redoc", "openapi.json")
        ):
            raise HTTPException(status_code=404, detail="Not Found")

        # Resolve path safely inside dist_dir to prevent path traversal
        try:
            resolved_candidate = (dist_dir / full_path).resolve()
            if not str(resolved_candidate).startswith(str(dist_dir.resolve())):
                raise HTTPException(status_code=400, detail="Invalid path")
            if resolved_candidate.is_file():
                return FileResponse(resolved_candidate)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid path")

        return FileResponse(index_html)
