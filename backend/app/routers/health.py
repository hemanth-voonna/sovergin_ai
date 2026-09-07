"""Liveness/health API — intentionally unauthenticated."""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas import HealthOut
from .dashboard import system_health

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthOut)
def health():
    return HealthOut(**system_health())