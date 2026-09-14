# ============================================================
# FILE: backend/app/api/deps.py
# Authentication & authorization dependencies.
# ============================================================

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core import firebase
from backend.app.db.enums import UserRole
from backend.app.db.models.user import User
from backend.app.db.session import get_db

# auto_error=False: a missing header should 401 like an invalid one, not the
# library's default 403 — the frontend treats 401 (not 403) as "not signed
# in, go to /login", reserving 403 for "signed in but not allowed".
bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_verified_firebase_claims(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict[str, Any]:
    """Verifies the bearer token against Firebase and returns its claims.

    Kept as its own dependency (rather than inlined into get_current_user)
    so tests can override just this seam via app.dependency_overrides,
    without needing a real Firebase project or the Auth Emulator.
    """
    if creds is None:
        raise _CREDENTIALS_EXC
    try:
        return firebase.verify_id_token(creds.credentials)
    except Exception:  # noqa: BLE001 — any firebase_admin.auth.* verification error
        raise _CREDENTIALS_EXC


def get_current_user(
    claims: Annotated[dict[str, Any], Depends(get_verified_firebase_claims)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    uid = claims.get("uid")
    if not uid:
        raise _CREDENTIALS_EXC

    user = db.query(User).filter(User.firebase_uid == uid).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This Firebase account has no ArthSetu profile — contact an administrator.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: UserRole):
    """Dependency: the current user's role must be >= `minimum`."""

    def _dep(user: CurrentUser) -> User:
        current = user.role if isinstance(user.role, UserRole) else UserRole(user.role)
        if not current.satisfies(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum.value} role",
            )
        return user

    return _dep


require_reviewer = require_role(UserRole.REVIEWER)
require_admin = require_role(UserRole.ADMIN)

ReviewerUser = Annotated[User, Depends(require_reviewer)]
AdminUser = Annotated[User, Depends(require_admin)]
