"""
Equipment Failure Model
Menyimpan history equipment failure/kerusakan peralatan SCADA.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text

from app.db.base import Base


class EquipmentFailure(Base):
    """
    Model untuk menyimpan equipment failure report.
    
    Table ini menyimpan history semua equipment failure yang terdeteksi
    dari PLC atau di-report melalui API.
    
    Untuk menghindari duplicate data, hanya menyimpan jika:
    - Equipment code berbeda, ATAU
    - Timestamp berbeda, ATAU
    - Description berbeda
    """
    __tablename__ = "equipment_failure"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    
    # Equipment identification
    equipment_code = Column(String(64), nullable=False, index=True)
    equipment_name = Column(String(128), nullable=True)
    
    # Failure information
    description = Column(Text, nullable=False)
    failure_type = Column(String(64), nullable=True)  # Optional: categorize failure type
    
    # Timestamps
    failure_date = Column(DateTime, nullable=False, index=True)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    
    # Status tracking
    is_resolved = Column(
        Boolean,
        default=False,
        nullable=False,
        server_default=text("false"),
    )
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Metadata
    source = Column(String(32), default="plc", nullable=False)  # 'plc', 'api', 'manual'
    severity = Column(String(32), default="medium", nullable=False)  # 'low', 'medium', 'high', 'critical'
    
    # Indexes untuk optimasi query
    __table_args__ = (
        Index(
            "ix_equipment_failure_equipment_date",
            "equipment_code",
            "failure_date",
        ),
        Index(
            "ix_equipment_failure_created_at",
            "created_at",
        ),
        UniqueConstraint(
            "equipment_code",
            "failure_date",
            "description",
            name="uq_equipment_failure_unique_report",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<EquipmentFailure(id={self.id}, "
            f"equipment_code={self.equipment_code}, "
            f"failure_date={self.failure_date})>"
        )
