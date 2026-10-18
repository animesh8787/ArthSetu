from sqlalchemy import Float, String
from sqlalchemy.orm import mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import UUIDPKMixin, TimestampMixin


class MatchingConfig(Base, UUIDPKMixin, TimestampMixin):
    """Tunable matching-engine weights (single-row table).

    Started out as fixed constants in matching_engine.py; moved here so an
    admin can calibrate them from reviewer approve/reject feedback (see
    /matching/calibration) without a deploy.
    """

    __tablename__ = "matching_config"

    gstin_weight = mapped_column(Float, default=0.60, nullable=False)
    pan_weight = mapped_column(Float, default=0.55, nullable=False)
    name_weight = mapped_column(Float, default=0.42, nullable=False)
    address_weight = mapped_column(Float, default=0.28, nullable=False)
    pin_weight = mapped_column(Float, default=0.12, nullable=False)
    contact_weight = mapped_column(Float, default=0.06, server_default="0.06", nullable=False)
    pin_requires_name_sim = mapped_column(Float, default=0.35, nullable=False)
    auto_link_threshold = mapped_column(Float, default=0.92, nullable=False)
    review_threshold = mapped_column(Float, default=0.70, nullable=False)

    updated_by = mapped_column(String(100), nullable=True)
