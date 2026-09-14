from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.enums import UserRole
from backend.app.db.mixins import UUIDPKMixin, TimestampMixin
from backend.app.db.types import str_enum


class User(Base, UUIDPKMixin, TimestampMixin):
    # "user" is a reserved word in PostgreSQL — use a safe table name.
    __tablename__ = "user_account"

    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    role = mapped_column(
        str_enum(UserRole, "userrole"),
        default=UserRole.VIEWER,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
