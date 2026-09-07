"""Secure sandbox API."""
from __future__ import annotations

from fastapi import APIRouter

from ..activity import log_event
from sandbox.executor import run_code
from ..schemas import SandboxRunIn, SandboxRunOut
from . import deps  # noqa: F401

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"], dependencies=[deps.auth])


@router.post("/run", response_model=SandboxRunOut)
def sandbox_run(payload: SandboxRunIn):
    result = run_code(
        code=payload.code,
        language=payload.language,
        timeout=payload.timeout,
        memory_mb=payload.memory_mb,
    )
    log_event(
        "sandbox",
        f"Sandbox run ({payload.language}): {result.status} in {result.duration_ms}ms",
        details={"status": result.status, "exit_code": result.exit_code,
                 "duration_ms": result.duration_ms, "language": payload.language},
    )
    return SandboxRunOut(**result.to_dict())