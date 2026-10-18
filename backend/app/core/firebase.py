# ============================================================
# FILE: backend/app/core/firebase.py
# Single seam onto the Firebase Admin SDK: token verification +
# server-side user management. Whether this talks to a real Firebase
# project or the local Auth Emulator is decided entirely by env vars
# (FIREBASE_CREDENTIALS_JSON vs FIREBASE_AUTH_EMULATOR_HOST) — nothing
# else in the codebase needs to know which one is active.
# ============================================================

from __future__ import annotations

import json
import os
import threading
from functools import lru_cache
from typing import Any

import firebase_admin
from firebase_admin import auth as _auth
from firebase_admin import credentials

from backend.app.core.config import settings

# Re-exported so callers can do `from backend.app.core.firebase import auth`
# and use it exactly like the SDK's own `firebase_admin.auth` module
# (create_user, update_user, get_user_by_email, UserNotFoundError, ...).
auth = _auth


_init_lock = threading.Lock()


def _app() -> firebase_admin.App:
    # lru_cache alone lets two threads race into initialize_app on first use.
    with _init_lock:
        return _build_app()


@lru_cache(maxsize=1)
def _build_app() -> firebase_admin.App:
    if settings.FIREBASE_AUTH_EMULATOR_HOST:
        # firebase-admin reads the emulator host from the process environment,
        # and pydantic-settings never writes .env values back to it.
        os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", settings.FIREBASE_AUTH_EMULATOR_HOST)
    if settings.FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
        return firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
    # No credentials: relies on FIREBASE_AUTH_EMULATOR_HOST being set (the
    # Admin SDK reads it directly), so this path is only safe for local
    # dev/test — config.py's production validator refuses to boot without
    # FIREBASE_CREDENTIALS_JSON set.
    return firebase_admin.initialize_app(options={"projectId": settings.FIREBASE_PROJECT_ID})


def verify_id_token(token: str) -> dict[str, Any]:
    """Raises firebase_admin.auth.* errors (InvalidIdTokenError, ExpiredIdTokenError, ...) on failure."""
    return _auth.verify_id_token(token, app=_app())


def create_user(*, email: str, password: str) -> _auth.UserRecord:
    """Raises auth.EmailAlreadyExistsError if the email is already registered."""
    return _auth.create_user(email=email, password=password, app=_app())


def update_user(uid: str, **changes: Any) -> _auth.UserRecord:
    """Raises auth.UserNotFoundError if uid doesn't exist."""
    return _auth.update_user(uid, app=_app(), **changes)


def get_user_by_email(email: str) -> _auth.UserRecord:
    """Raises auth.UserNotFoundError if no such user exists."""
    return _auth.get_user_by_email(email, app=_app())


def delete_user(uid: str) -> None:
    _auth.delete_user(uid, app=_app())
