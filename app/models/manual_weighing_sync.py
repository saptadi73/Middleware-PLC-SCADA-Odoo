from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ManualWeighingSync(Base):
    __tablename__ = "manual_weighing_sync"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    reference_key = Column(String(32), nullable=False, index=True)
    handshake_address = Column(Integer, nullable=False, index=True)
    batch_no = Column(Integer, nullable=True)
    mo_id = Column(String(64), nullable=False, index=True)
    product_id = Column(Integer, nullable=False)
    consumption = Column(Float, nullable=False)
    payload_hash = Column(String(64), nullable=False, index=True)
    status = Column(
        String(32),
        nullable=False,
        server_default=text("'pending_handshake'"),
    )
    last_error = Column(Text, nullable=True)
    odoo_synced_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    handshake_marked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index(
            "ix_manual_weighing_sync_pending_lookup",
            "payload_hash",
            "reference_key",
            "handshake_address",
            "handshake_marked_at",
        ),
    )
