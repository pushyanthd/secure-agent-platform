"""Loopback-only authenticated JSON API. Credentials never enter worker configuration."""

import asyncio
import hashlib
import secrets
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field, model_validator
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agentguard.artifact_volume import ArtifactVolumeUnavailable
from agentguard.contracts import Contract
from agentguard.control import ControlError, ControlPlane, Principal, ReviewAction, SubmitRun
from agentguard.storage import ReviewRejected
from agentguard.ui import UI_SECURITY_HEADERS, install_ui

SECURITY_HEADERS = {
    "cache-control": "no-store",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Credential(Contract):
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    principal: Principal


class Credentials(Contract):
    entries: tuple[Credential, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def unique_tokens(self) -> "Credentials":
        if len({entry.token_sha256 for entry in self.entries}) != len(self.entries):
            raise ValueError("Duplicate credential")
        identities: dict[str, tuple[str, str]] = {}
        for entry in self.entries:
            principal = entry.principal
            identity = (principal.actor, principal.workspace)
            if principal.subject in identities and identities[principal.subject] != identity:
                raise ValueError("A subject must have a single actor/workspace identity")
            identities[principal.subject] = identity
        return self


class SecurityBoundary:
    """Check exact Host/Origin, bearer authority, CSRF header and actual body size."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        credentials: Credentials,
        origin: str,
        public_paths: frozenset[str] = frozenset(),
    ):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Control plane requires http://127.0.0.1:<port>")
        self.app, self.credentials, self.origin, self.host = app, credentials, origin, parsed.netloc
        self.public_paths = public_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        public = scope["method"] in {"GET", "HEAD"} and scope["path"] in self.public_paths

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.update(UI_SECURITY_HEADERS if public else SECURITY_HEADERS)
            await send(message)

        async def reject(status: int, code: str) -> None:
            response = JSONResponse({"error": code}, status_code=status)
            await response(scope, receive, secure_send)

        counts = Counter(key.lower() for key, _ in scope["headers"])
        if any(
            counts[key] > 1
            for key in (
                b"host",
                b"authorization",
                b"origin",
                b"content-type",
                b"content-length",
                b"x-agentguard-request",
                b"sec-fetch-site",
            )
        ):
            await reject(400, "DUPLICATE_HEADER")
            return
        headers = Headers(scope=scope)
        if headers.get("host") != self.host:
            await reject(400, "INVALID_HOST")
            return
        if headers.get("origin") not in (None, self.origin) or headers.get(
            "sec-fetch-site"
        ) not in (None, "same-origin", "none"):
            await reject(403, "CROSS_ORIGIN_FORBIDDEN")
            return
        if public:
            await self.app(scope, receive, secure_send)
            return
        authorization = headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or not 32 <= len(authorization) <= 512:
            await reject(401, "AUTHENTICATION_REQUIRED")
            return
        fingerprint = token_hash(authorization[7:])
        principal = next(
            (
                entry.principal
                for entry in self.credentials.entries
                if secrets.compare_digest(fingerprint, entry.token_sha256)
            ),
            None,
        )
        if principal is None:
            await reject(401, "AUTHENTICATION_REQUIRED")
            return
        scope.setdefault("state", {})["principal"] = principal
        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            if headers.get("x-agentguard-request") != "1":
                await reject(403, "CSRF_HEADER_REQUIRED")
                return
            if headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
                await reject(415, "JSON_REQUIRED")
                return
        # Buffer at most 16 KiB, including chunked bodies; Content-Length is not trusted.
        body = bytearray()
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > 16384:
                        await reject(413, "BODY_TOO_LARGE")
                        return
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await reject(408, "REQUEST_TIMEOUT")
            return

        async def buffered_receive() -> Message:
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, buffered_receive, secure_send)


def create_app(
    control: ControlPlane,
    credentials: Credentials,
    *,
    origin: str,
    ui_directory: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="AgentGuard control plane", docs_url=None, redoc_url=None, openapi_url=None)
    public_paths = install_ui(app, ui_directory or Path(__file__).with_name("ui"))
    app.add_middleware(
        SecurityBoundary, credentials=credentials, origin=origin, public_paths=public_paths
    )

    @app.exception_handler(ControlError)
    async def control_error(request: Request, exc: ControlError) -> JSONResponse:
        return JSONResponse({"error": exc.code}, status_code=exc.status)

    @app.exception_handler(ReviewRejected)
    async def review_error(request: Request, exc: ReviewRejected) -> JSONResponse:
        return JSONResponse({"error": "APPROVAL_STALE_OR_INVALID"}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default includes input values, which may contain reviewer credentials.
        return JSONResponse({"error": "INVALID_REQUEST"}, status_code=422)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
            return JSONResponse({"error": "ARTIFACT_STORAGE_FULL"}, status_code=507)
        return JSONResponse({"error": "STORAGE_UNAVAILABLE"}, status_code=503)

    @app.exception_handler(ArtifactVolumeUnavailable)
    async def volume_error(request: Request, exc: ArtifactVolumeUnavailable) -> JSONResponse:
        return JSONResponse({"error": "ARTIFACT_VOLUME_UNAVAILABLE"}, status_code=503)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        # The outer server-error handler bypasses user middleware on unhandled errors.
        return JSONResponse({"error": "INTERNAL_ERROR"}, status_code=500, headers=SECURITY_HEADERS)

    @app.get("/api/identity")
    def identity(request: Request) -> dict[str, Any]:
        principal: Principal = request.state.principal
        return principal.model_dump() | {"mode": control.mode, "profile": "defended"}

    @app.get("/api/scenarios")
    def scenarios(request: Request) -> list[dict[str, Any]]:
        return control.scenarios(request.state.principal)

    @app.post("/api/runs", status_code=201)
    def submit(
        request: Request,
        body: SubmitRun,
        idempotency_key: Annotated[str, Header(pattern=r"^[a-zA-Z0-9_-]{8,128}$")],
    ) -> dict[str, str]:
        episode = control.submit(request.state.principal, body, idempotency_key)
        return {"episode_id": episode}

    @app.get("/api/runs")
    def runs(
        request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50
    ) -> list[dict[str, Any]]:
        return control.runs(request.state.principal, limit=limit)

    @app.get("/api/runs/{episode}")
    def detail(request: Request, episode: str) -> dict[str, Any]:
        return control.detail(request.state.principal, episode)

    @app.get("/api/runs/{episode}/timeline")
    def timeline(request: Request, episode: str) -> list[dict[str, Any]]:
        return control.timeline(request.state.principal, episode)

    @app.post("/api/runs/{episode}/cancel")
    def cancel(request: Request, episode: str) -> dict[str, str]:
        return {"status": control.cancel(request.state.principal, episode)}

    @app.get("/api/runs/{episode}/approvals")
    def approvals(request: Request, episode: str) -> list[dict[str, Any]]:
        return control.approvals(request.state.principal, episode)

    @app.get("/api/runs/{episode}/approvals/{approval}")
    def approval(request: Request, episode: str, approval: str) -> dict[str, Any]:
        return control.approval(request.state.principal, episode, approval)

    @app.post("/api/runs/{episode}/approvals/{approval}/review")
    def review(request: Request, episode: str, approval: str, body: ReviewAction) -> dict[str, str]:
        control.review(request.state.principal, episode, approval, body)
        return {"status": "APPROVED" if body.approve else "REJECTED"}

    return app
