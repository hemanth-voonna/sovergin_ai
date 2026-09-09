"""Authentication router."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginRequestIn, TokenOut, UserOut
from ..security import (
    create_access_token,
    decode_access_token,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(credentials: LoginRequestIn, db: Session = Depends(get_db)):
    """Authenticate user with username and password."""
    username = credentials.username.strip()
    user = db.query(User).filter(User.username == username).first()

    if not user or not user.is_active or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token({"sub": user.username})
    logger.info("User logged in successfully: %s", user.username)

    return TokenOut(
        access_token=token,
        token_type="bearer",
        username=user.username,
        full_name=user.full_name or user.username,
    )


@router.get("/me", response_model=UserOut)
def get_me(request: Request, db: Session = Depends(get_db)):
    """Get profile of current authenticated user."""
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    username = payload["sub"]
    user = db.query(User).filter(User.username == username).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled.",
        )

    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
    )


@router.post("/logout")
def logout():
    """Acknowledge logout."""
    return {"status": "ok", "message": "Logged out successfully."}
