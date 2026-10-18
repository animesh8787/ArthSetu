# ============================================================
# FILE: backend/app/services/user_service.py
# ============================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core import firebase
from backend.app.core.config import settings
from backend.app.db.enums import UserRole
from backend.app.db.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.email.asc()).all()


def create_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    role: str = "viewer",
    adopt_existing: bool = False,
) -> User:
    """Create the Firebase identity and the local profile.

    ``adopt_existing`` links an already-registered Firebase account instead of
    failing - used by the bootstrap admin when the database was reset but the
    Firebase project was not. An adopted account is never deleted on failure.
    """
    if get_by_email(db, email):
        raise ValueError("Email already exists")

    adopted = False
    try:
        record = firebase.create_user(email=email, password=password)
    except firebase.auth.EmailAlreadyExistsError:
        if not adopt_existing:
            raise ValueError("Email already exists")
        record = firebase.get_user_by_email(email)
        adopted = True

    try:
        user = User(
            email=email,
            full_name=full_name,
            role=UserRole(role),
            firebase_uid=record.uid,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        # Local row failed - don't leave an orphaned Firebase account behind,
        # or retrying with the same email hits EmailAlreadyExistsError forever.
        db.rollback()
        if not adopted:
            firebase.delete_user(record.uid)
        raise
    return user


def _get(db: Session, user_id: str) -> User:
    try:
        uid = UUID(str(user_id))
    except (ValueError, TypeError):
        raise ValueError("Invalid user id")
    user = db.get(User, uid)
    if not user:
        raise ValueError("User not found")
    return user


def _is_bootstrap(user: User) -> bool:
    return user.email.lower() == settings.BOOTSTRAP_ADMIN_EMAIL.lower()


def update_user(db: Session, user_id: str, **changes) -> User:
    user = _get(db, user_id)

    # The bootstrap admin must always remain an active admin, reachable at
    # the email BOOTSTRAP_ADMIN_EMAIL is set to — so its email can't move
    # either, or the bootstrap check below would stop recognising it.
    if _is_bootstrap(user):
        if changes.get("is_active") is False:
            raise ValueError("The bootstrap admin cannot be disabled")
        if changes.get("role") not in (None, "admin"):
            raise ValueError("The bootstrap admin cannot be demoted")
        if changes.get("email") not in (None, user.email):
            raise ValueError("The bootstrap admin's email cannot be changed")

    new_email = changes.get("email")
    if new_email is not None and new_email != user.email:
        if get_by_email(db, new_email):
            raise ValueError("Email already exists")
        # Firebase owns sign-in, so the login email must move there first.
        try:
            firebase.update_user(user.firebase_uid, email=new_email)
        except firebase.auth.EmailAlreadyExistsError:
            raise ValueError("Email already exists")
        except firebase.auth.UserNotFoundError:
            raise ValueError("User not found in Firebase")

    if changes.get("role") is not None:
        user.role = UserRole(changes["role"])
    for field in ("full_name", "email", "is_active"):
        if changes.get(field) is not None:
            setattr(user, field, changes[field])
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user_id: str, new_password: str) -> User:
    user = _get(db, user_id)
    try:
        firebase.update_user(user.firebase_uid, password=new_password)
    except firebase.auth.UserNotFoundError:
        raise ValueError("User not found in Firebase")
    return user


def to_out(user: User) -> dict:
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "role": role,
        "is_active": user.is_active,
        "is_bootstrap": _is_bootstrap(user),
        "created_at": user.created_at,
    }
