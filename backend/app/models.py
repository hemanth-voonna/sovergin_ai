"""ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(255), index=True)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    file_type: Mapped[str] = mapped_column(String(16), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(String(64), default="")

    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    # uploaded | validating | processing | processed | indexing | indexed | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    validation_status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | valid | warning | invalid | not_applicable

    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages_data: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    def to_dict(self, include_text: bool = False) -> dict:
        data = {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "status": self.status,
            "error_message": self.error_message,
            "ocr_used": self.ocr_used,
            "page_count": self.page_count,
            "char_count": self.char_count,
            "chunk_count": self.chunk_count,
            "validation_status": self.validation_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_text:
            data["extracted_text"] = self.extracted_text
            data["pages_data"] = self.pages_data
        return data


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    # upload | process | index | rag_query | agent_run | validation | ocr | sandbox | delete | system
    actor: Mapped[str] = mapped_column(String(64), default="user")
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(String(500), default="")
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "actor": self.actor,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }