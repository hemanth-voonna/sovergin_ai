"""Activity logging — a lightweight audit trail shown on the dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from .database import SessionLocal
from .models import Activity

ACTION_LABELS = {
    "upload": "Document uploaded",
    "process": "Document processed",
    "index": "Document indexed",
    "rag_query": "RAG query",
    "agent_run": "Agent executed",
    "validation": "Document validated",
    "ocr": "OCR completed",
    "sandbox": "Sandbox execution",
    "delete": "Document deleted",
    "system": "System",
}


def log_event(
    action: str,
    message: str,
    actor: str = "user",
    entity_type: str = "",
    entity_id: str = "",
    details: dict | None = None,
) -> None:
    try:
        db = SessionLocal()
        try:
            db.add(
                Activity(
                    action=action,
                    actor=actor,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    message=message[:500],
                    details=details,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:  # logging must never break the main flow
        pass


def recent_activity(limit: int = 12) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(Activity).order_by(Activity.created_at.desc()).limit(limit)
        ).all()
        return [r.to_dict() for r in rows]
    finally:
        db.close()


def activity_series(days: int = 7) -> list[dict]:
    """Per-day action counts for the dashboard chart."""
    db = SessionLocal()
    try:
        start = datetime.now(timezone.utc) - timedelta(days=days - 1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        rows = db.execute(
            select(
                func.date(Activity.created_at).label("day"),
                func.count(Activity.id).label("n"),
            )
            .where(Activity.created_at >= start)
            .group_by("day")
            .order_by("day")
        ).all()
        by_day = {str(day): n for day, n in rows}
        series = []
        for i in range(days):
            day = (start + timedelta(days=i)).date().isoformat()
            series.append({"day": day, "count": by_day.get(day, 0)})
        return series
    finally:
        db.close()