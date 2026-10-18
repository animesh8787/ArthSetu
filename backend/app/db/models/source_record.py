from sqlalchemy import ForeignKey, String, UniqueConstraint, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.db.mixins import UUIDPKMixin, TimestampMixin

class SourceRecord(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "source_record"

    source_system_id = mapped_column(ForeignKey("source_system.id"))
    external_id = mapped_column(String(255), nullable=False)

    raw_payload = mapped_column(JSON, nullable=False)
    normalized_payload = mapped_column(JSON)

    extracted_name = mapped_column(String(255))
    extracted_pan = mapped_column(String(20), index=True)
    extracted_gstin = mapped_column(String(20), index=True)
    extracted_address = mapped_column(String(500), nullable=True)
    extracted_pin = mapped_column(String(6), index=True, nullable=True)
    extracted_email = mapped_column(String(255), nullable=True)
    extracted_phone = mapped_column(String(20), nullable=True)

    source_system = relationship("SourceSystem", back_populates="records")
    links = relationship("EntityRecordLink", back_populates="source_record")

    __table_args__ = (
        UniqueConstraint("source_system_id", "external_id"),
        Index("ix_sr_name", "extracted_name"),
    )