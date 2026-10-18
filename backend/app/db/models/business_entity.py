from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.db.enums import EntityStatusEnum
from backend.app.db.mixins import UUIDPKMixin, TimestampMixin
from backend.app.db.types import str_enum


class BusinessEntity(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "business_entity"

    ubid_code = mapped_column(String(50), unique=True, index=True)

    legal_name = mapped_column(String(255))
    normalized_name = mapped_column(String(255), index=True)

    pan = mapped_column(String(20), unique=True, nullable=True)
    gstin = mapped_column(String(20), unique=True, nullable=True)

    address = mapped_column(String(500), nullable=True)
    normalized_address = mapped_column(String(500), index=True, nullable=True)
    pin_code = mapped_column(String(6), index=True, nullable=True)

    email = mapped_column(String(255), nullable=True)
    phone = mapped_column(String(20), nullable=True)

    district = mapped_column(String(100), index=True, nullable=True)
    sector = mapped_column(String(100), nullable=True)

    status = mapped_column(
        str_enum(EntityStatusEnum, "entitystatusenum"),
        default=EntityStatusEnum.UNKNOWN,
        index=True,
    )

    # A reviewer can pin the status; the engine then records its opinion in a
    # snapshot but leaves `status` untouched until the lock is cleared.
    status_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    status_override_reason = mapped_column(String(500), nullable=True)
    status_overridden_by = mapped_column(String(100), nullable=True)

    links = relationship("EntityRecordLink", back_populates="business_entity")
    activities = relationship("ActivityEvent", back_populates="business_entity")
    snapshots = relationship("StatusSnapshot", order_by="StatusSnapshot.created_at")
