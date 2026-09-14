# ============================================================
# FILE: backend/app/api/v1/routes/auth.py
# Sign-in itself happens client-side against Firebase; this router only
# covers the local ArthSetu profile (role, active status) layered on top
# of a verified Firebase identity, plus admin-driven user management.
# ============================================================

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import AdminUser, CurrentUser
from backend.app.db.session import get_db
from backend.app.schemas import (
    PasswordResetRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from backend.app.services import user_service

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser):
    return UserOut(**user_service.to_out(current_user))


# ------------------------------------------------------------
# Admin — user management
# ------------------------------------------------------------

@router.get("/users", response_model=list[UserOut])
def list_users(_: AdminUser, db: DbSession):
    return [UserOut(**user_service.to_out(u)) for u in user_service.list_users(db)]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, _: AdminUser, db: DbSession):
    try:
        user = user_service.create_user(
            db,
            email=body.email,
            full_name=body.full_name,
            password=body.password,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return UserOut(**user_service.to_out(user))


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    _: AdminUser,
    db: DbSession,
):
    try:
        user = user_service.update_user(db, user_id, **body.model_dump())
    except ValueError as exc:
        code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=code, detail=str(exc))
    return UserOut(**user_service.to_out(user))


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: str,
    body: PasswordResetRequest,
    _: AdminUser,
    db: DbSession,
):
    try:
        user = user_service.set_password(db, user_id, body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return UserOut(**user_service.to_out(user))
