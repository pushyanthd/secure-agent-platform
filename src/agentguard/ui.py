"""Serve only the compiled public application shell, never workspace files."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, PlainTextResponse

UI_SECURITY_HEADERS = {
    "cache-control": "no-store",
    "content-security-policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'; object-src 'none'"
    ),
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


def install_ui(app: FastAPI, directory: Path) -> frozenset[str]:
    """Freeze an exact route allowlist at startup; API auth has no prefix bypass."""
    root = directory.resolve()
    files: dict[str, Path] = {}
    index = root / "index.html"
    if index.is_file() and index.resolve().is_relative_to(root):
        files["/"] = index
        for asset in (root / "assets").glob("*"):
            if (
                asset.is_file()
                and asset.suffix in {".js", ".css"}
                and asset.resolve().is_relative_to(root)
            ):
                files[f"/assets/{asset.name}"] = asset

    async def shell(request: Request) -> FileResponse | PlainTextResponse:
        file = files.get(request.url.path)
        if file is None or not file.is_file() or not file.resolve().is_relative_to(root):
            return PlainTextResponse(
                "Operator UI is not built. Run make ui-setup ui-build, then restart the API.",
                status_code=503,
            )
        return FileResponse(file)

    paths = frozenset({"/", *files})
    for path in sorted(paths):
        app.add_api_route(path, shell, methods=["GET", "HEAD"], response_model=None)
    return paths
