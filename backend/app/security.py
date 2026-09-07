"""Security helpers: file validation, magic-byte checks, optional API-key auth."""
from __future__ import annotations

import hashlib
import logging
import re
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


# ------------------------------------------------------------------ Optional auth
async def require_api_key(request: Request) -> None:
    """If ACCESS_TOKEN is configured, every request must carry it.

    Frontend sends `Authorization: Bearer <token>`. Health checks are exempt
    (they only expose non-sensitive liveness data) -- routers that include
    this dependency decide their own scope.
    """
    if not settings.auth_enabled:
        return
    header = request.headers.get("authorization", "")
    provided = header.removeprefix("Bearer ").strip()
    if provided != settings.ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
        )


def get_auth_dependency():
    return Depends(require_api_key)
