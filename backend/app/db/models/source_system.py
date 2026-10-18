from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.db.mixins import UUIDPKMixin, TimestampMixin

class SourceSystem(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "source_system"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(255))

    # Optional read-only connector: a CSV/JSON export this system publishes, which the
    # scheduled sync pulls (records or activity events). Nothing is ever written back.
    pull_url = mapped_column(String(1000), nullable=True)
    pull_kind = mapped_column(String(10), nullable=True)  # "records" | "events"
    last_pull_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_pull_status = mapped_column(String(500), nullable=True)

    records = relationship("SourceRecord", back_populates="source_system")