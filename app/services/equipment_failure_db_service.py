"""
Equipment Failure Database Service
Menyimpan equipment failure ke database hanya jika data berubah.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment_failure import EquipmentFailure

logger = logging.getLogger(__name__)


class EquipmentFailureDbService:
    """Service untuk menyimpan equipment failure ke database."""

    def __init__(self, db: Session):
        self.db = db

    def _find_last_record(self, equipment_code: str) -> Optional[EquipmentFailure]:
        """Cari record terakhir untuk equipment_code tertentu."""
        stmt = (
            select(EquipmentFailure)
            .where(EquipmentFailure.equipment_code == equipment_code)
            .order_by(EquipmentFailure.failure_date.desc())
            .limit(1)
        )
        result = self.db.execute(stmt)
        return result.scalars().first()

    def _normalize_text(self, value: Optional[str]) -> str:
        """Normalize text untuk perbandingan."""
        return (value or "").replace("\x00", "").strip()

    def _is_changed(
        self,
        last_record: EquipmentFailure,
        equipment_code: str,
        description: str,
        failure_date: datetime,
    ) -> bool:
        """Check apakah data failure berubah dibanding record terakhir."""
        if last_record.equipment_code != equipment_code:
            return True
        if last_record.failure_date != failure_date:
            return True
        if self._normalize_text(last_record.description) != self._normalize_text(description):
            return True
        return False

    def save_if_changed(
        self,
        equipment_code: str,
        description: str,
        failure_date: datetime,
        equipment_name: Optional[str] = None,
        source: str = "plc",
        severity: str = "medium",
        failure_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Simpan equipment failure jika data berubah.
        
        Returns:
            {
                "saved": True/False,
                "reason": "...",
                "record_id": "..." (optional)
            }
        """
        try:
            last_record = self._find_last_record(equipment_code)
            if last_record and not self._is_changed(
                last_record,
                equipment_code=equipment_code,
                description=description,
                failure_date=failure_date,
            ):
                return {
                    "saved": False,
                    "reason": "No change in failure data",
                    "record_id": str(last_record.id),
                }

            clean_equipment_code = self._normalize_text(equipment_code)
            clean_description = self._normalize_text(description)

            new_record = EquipmentFailure(
                equipment_code=clean_equipment_code,
                equipment_name=self._normalize_text(equipment_name),
                description=clean_description,
                failure_date=failure_date,
                source=source,
                severity=severity,
                failure_type=failure_type,
            )

            self.db.add(new_record)
            self.db.commit()
            self.db.refresh(new_record)

            logger.info(
                "✓ Equipment failure saved: %s (%s)",
                equipment_code,
                failure_date,
            )
            return {
                "saved": True,
                "reason": "New failure data saved",
                "record_id": str(new_record.id),
            }

        except Exception as exc:
            self.db.rollback()
            logger.error("Error saving equipment failure: %s", str(exc))
            return {
                "saved": False,
                "reason": f"Error: {str(exc)}",
            }
