from sqlalchemy import ForeignKey, Float, Index, JSON
from sqlalchemy.orm import mapped_column, relationship

from backend.app.db.base import Base
from backend.app.db.enums import LinkDecisionEnum
from backend.app.db.mixins import UUIDPKMixin, TimestampMixin
from backend.app.db.types import str_enum


class EntityRecordLink(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "entity_record_link"

    # One link per record: a record belongs to exactly one business.
    source_record_id = mapped_column(
        ForeignKey("source_record.id"), index=True, unique=True
    )
    business_entity_id = mapped_column(
        ForeignKey("business_entity.id"), index=True
    )

    confidence = mapped_column(Float)
    decision = mapped_column(str_enum(LinkDecisionEnum, "linkdecisionenum"), index=True)
    explanation = mapped_column(JSON)

    source_record = relationship("SourceRecord", back_populates="links")
    business_entity = relationship("BusinessEntity", back_populates="links")

    __table_args__ = (
        Index("ix_link_confidence", "confidence"),
    )
