"""Security helpers: file validation, magic-byte checks, authentication."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status

from .config import settings

logger = logging.getLogger(__name__)

MAX_SAFE_FILENAME_LEN = 120

# Signature checks (magic bytes) per allowed extension.
MAGIC_BYTES: dict[str, list[bytes]] = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "docx": [b"PK\x03\x04"],
    "txt": [],  # no fixed signature
}

# docx is a zip; require the OOXML content-type marker inside.
DOCX_MARKER = b"[Content_Types].xml"

AUTH_SECRET_KEY = getattr(settings, "ACCESS_TOKEN", "") or "sovereignai-workbench-secret-key-2026"
TOKEN_EXPIRE_SECONDS = 7 * 24 * 3600  # 7 days


class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def safe_filename(name: str) -> str:
    """Keep only safe characters and a short length."""
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name[:MAX_SAFE_FILENAME_LEN]
    return name or "document"


def file_signature(data: bytes) -> bytes:
    return data[:16]


def validate_upload(filename: str, content: bytes) -> str:
    """Validate extension, size and magic bytes. Returns the file type."""
    if len(content) == 0:
        raise ValidationError("Uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise ValidationError(
            f"File exceeds the {settings.MAX_UPLOAD_MB} MB size limit."
        )

    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions:
        raise ValidationError(
            f"File type '.{ext}' is not allowed. Allowed: {', '.join(sorted(settings.allowed_extensions))}."
        )

    sig = file_signature(content)
    expected = MAGIC_BYTES.get(ext, [])
    if expected and not any(sig.startswith(m) for m in expected):
        raise ValidationError(
            f"File content does not match its '.{ext}' extension (magic-byte check failed)."
        )
    if ext == "docx" and DOCX_MARKER not in content:
        raise ValidationError("DOCX file is corrupt or not a valid Office document.")

    return ext


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ------------------------------------------------------------------ Password helpers
def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, key_hex = hashed_password.split(":", 1)
        computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), bytes.fromhex(salt), 100_000)
        return hmac.compare_digest(computed.hex(), key_hex)
    except Exception:
        return False


# ------------------------------------------------------------------ Token helpers
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(s: str) -> bytes:
    pad = 4 - (len(s) % 4)
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def create_access_token(data: dict, expires_delta: int = TOKEN_EXPIRE_SECONDS) -> str:
    to_encode = data.copy()
    to_encode["exp"] = int(time.time()) + expires_delta
    payload_json = json.dumps(to_encode, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def decode_access_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ------------------------------------------------------------------ Request auth
async def require_api_key(request: Request) -> dict | None:
    """Validate Bearer token (user login token or ACCESS_TOKEN)."""
    header = request.headers.get("authorization", "")
    provided = header.removeprefix("Bearer ").strip()

    if provided:
        # Check user auth token
        payload = decode_access_token(provided)
        if payload:
            return payload
        # Check legacy static ACCESS_TOKEN
        if settings.auth_enabled and provided == settings.ACCESS_TOKEN:
            return {"sub": "api_client"}
        # Provided token was invalid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    if settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
        )

    return None


def get_auth_dependency():
    return Depends(require_api_key)

