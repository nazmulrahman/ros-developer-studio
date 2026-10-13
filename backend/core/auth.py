"""Token auth. Token is generated per process, printed once, never stored in source."""
import secrets
from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)
TOKEN = secrets.token_urlsafe(32)


def set_token(value: str) -> None:
    global TOKEN
    TOKEN = value


def _ok(candidate: str | None) -> bool:
    return bool(candidate) and secrets.compare_digest(candidate, TOKEN)


async def require_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if not creds or not _ok(creds.credentials):
        raise HTTPException(401, "Missing or invalid token")


def ws_authorized(ws: WebSocket) -> bool:
    return _ok(ws.query_params.get("token"))
