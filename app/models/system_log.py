from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class SystemLog(Base):
    __tablename__ = "system_log"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    level = Column(String(16), nullable=False, index=True)
    module = Column(String(255), nullable=False, index=True)
    message = Column(Text, nullable=False)
    batch_no = Column(String(64), nullable=True)
    mo_id = Column(String(64), nullable=True, index=True)

    __table_args__ = (
        Index("ix_system_log_level_timestamp", "level", "timestamp"),
        Index("ix_system_log_module_timestamp", "module", "timestamp"),
    )
